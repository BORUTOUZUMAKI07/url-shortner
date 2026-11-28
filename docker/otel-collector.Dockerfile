# Layer-2 collection agent for LinkForge — deployable as a Render web service
# or any Docker host. Pinned to a tag validated against this repo's config.
FROM otel/opentelemetry-collector-contrib:0.121.0

COPY otel-collector-config.yaml /etc/otelcol-contrib/config.yaml

# Default OTLP/HTTP ingest (Render injects a dynamic PORT; the config binds to
# ${env:PORT:-4318}). EXPOSE is documentary — Render routes to $PORT.
EXPOSE 4318
# OTLP/gRPC ingest (optional) + collector self-metrics + health endpoint.
EXPOSE 4317 8888 13133

CMD ["--config=/etc/otelcol-contrib/config.yaml"]