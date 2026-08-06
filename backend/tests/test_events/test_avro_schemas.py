import json
from datetime import datetime, timezone

import pytest

from src.shared.events.schemas import SCHEMA_DIR, deserialize, serialize


class TestAvroSchemas:
    def test_url_created_schema_file_exists(self):
        path = SCHEMA_DIR / "url-created.avsc"
        assert path.exists()
        with open(path) as f:
            schema = json.load(f)
        assert schema["name"] == "UrlCreated"
        fields = {f["name"]: f["type"] for f in schema["fields"]}
        assert "short_code" in fields
        assert "original_url" in fields
        assert "workspace_id" in fields
        assert "user_id" in fields
        assert "base_url" in fields

    def test_url_clicked_schema_file_exists(self):
        path = SCHEMA_DIR / "url-clicked.avsc"
        assert path.exists()
        with open(path) as f:
            schema = json.load(f)
        assert schema["name"] == "UrlClicked"
        fields = {f["name"]: f["type"] for f in schema["fields"]}
        assert "short_code" in fields
        assert "original_url" in fields
        assert "clicked_at" in fields
        assert "ip_address" in fields

    def test_serialize_roundtrip_url_created(self):
        original = {
            "short_code": "abc123",
            "original_url": "https://example.com",
            "workspace_id": 1,
            "user_id": 1,
            "base_url": "https://example.com",
        }
        data = serialize("url-created", original)
        assert isinstance(data, bytes)
        assert len(data) > 0

        decoded = deserialize("url-created", data)
        assert decoded["short_code"] == "abc123"
        assert decoded["original_url"] == "https://example.com"
        assert decoded["user_id"] == 1
        assert decoded["workspace_id"] == 1
        assert decoded["base_url"] == "https://example.com"

    def test_serialize_roundtrip_url_clicked(self):
        original = {
            "short_code": "abc123",
            "original_url": "https://example.com",
            "ip_address": "192.168.1.1",
            "user_agent": "Mozilla/5.0",
            "referer": "https://twitter.com",
            "clicked_at": datetime.now(timezone.utc).isoformat(),
        }
        data = serialize("url-clicked", original)
        assert isinstance(data, bytes)
        assert len(data) > 0

        decoded = deserialize("url-clicked", data)
        assert decoded["short_code"] == "abc123"
        assert decoded["ip_address"] == "192.168.1.1"
        assert decoded["clicked_at"] is not None

    def test_serialize_with_optional_fields(self):
        original = {
            "short_code": "optfields",
            "original_url": "https://example.com",
            "workspace_id": 1,
            "user_id": 42,
            "base_url": "https://example.com",
            "title": "My Title",
            "description": "A description",
            "tags": ["tag1", "tag2"],
        }
        data = serialize("url-created", original)
        decoded = deserialize("url-created", data)
        assert decoded["title"] == "My Title"
        assert decoded["description"] == "A description"
        assert decoded["tags"] == ["tag1", "tag2"]

    def test_unknown_topic_raises(self):
        with pytest.raises(FileNotFoundError):
            serialize("unknown-topic", {"key": "value"})

    def test_avro_decode_invalid_data_raises(self):
        with pytest.raises(Exception):
            deserialize("url-created", b"not valid avro data")

    def test_all_required_fields_present_url_created(self):
        data = serialize("url-created", {
            "short_code": "reqtest",
            "original_url": "https://reqtest.com",
            "workspace_id": 7,
            "user_id": 42,
            "base_url": "https://reqtest.com",
        })
        decoded = deserialize("url-created", data)
        assert decoded["short_code"] == "reqtest"
        assert decoded["user_id"] == 42
        assert decoded["workspace_id"] == 7
        assert decoded["base_url"] == "https://reqtest.com"
