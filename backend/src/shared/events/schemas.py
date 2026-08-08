import io
import json
import os
from pathlib import Path

import fastavro
import httpx

from src.shared import get_logger
from src.shared.core.config import settings

logger = get_logger(__name__)

SCHEMA_DIR = Path(__file__).resolve().parents[3] / "schemas" / "avro"

_schemas: dict[str, dict] = {}


def _load_schema(topic: str) -> dict:
    if topic not in _schemas:
        path = SCHEMA_DIR / f"{topic}.avsc"
        if not path.exists():
            raise FileNotFoundError(f"Avro schema not found: {path}")
        with open(path) as f:
            _schemas[topic] = json.load(f)
    return _schemas[topic]


def serialize(topic: str, value: dict[str, object]) -> bytes:
    schema = _load_schema(topic)
    buf = io.BytesIO()
    fastavro.schemaless_writer(buf, schema, value)
    return buf.getvalue()


def deserialize(topic: str, data: bytes) -> dict[str, object]:
    schema = _load_schema(topic)
    buf = io.BytesIO(data)
    try:
        return fastavro.schemaless_reader(buf, schema)  # type: ignore[return-value]
    except Exception as e:
        old_schema = _evolve_schema(schema)
        buf.seek(0)
        logger.warning(
            "Deserialization failed for topic %s with current schema (%s); retrying with evolved schema",
            topic,
            e,
        )
        return fastavro.schemaless_reader(buf, old_schema)  # type: ignore[return-value]


def _evolve_schema(schema: dict) -> dict:
    fields = []
    for f in schema["fields"]:
        if "default" not in f:
            fields.append(f)
    return {**schema, "fields": fields}


async def register_schemas():
    url = getattr(settings, "SCHEMA_REGISTRY_URL", None) or os.getenv("SCHEMA_REGISTRY_URL")
    if not url:
        return

    for topic in ("url-created", "url-clicked"):
        schema = _load_schema(topic)
        payload = {
            "schema": json.dumps(schema),
            "schemaType": "AVRO",
        }
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{url}/subjects/{topic}-value/versions",
                    json=payload,
                    timeout=10,
                )
                if resp.is_success:
                    logger.info("Registered schema for %s", topic)
                else:
                    logger.warning("Schema registration for %s: %s %s", topic, resp.status_code, resp.text)
        except Exception as e:
            logger.warning("Could not reach schema registry at %s: %s", url, e)


def get_schema(topic: str) -> dict:
    return _load_schema(topic)
