# Cloud Run image for the cop/thief MCP servers (assignment §6 stage-2).
# One image, two services: $MCP_ROLE selects the role, $PORT is set by Cloud Run.
# Build in the cloud with `gcloud run deploy --source .` (no local Docker needed).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    MCP_HOST=0.0.0.0 \
    MCP_ROLE=cop

WORKDIR /app

# Install the package + runtime deps (build needs pyproject + README + src).
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir .

# config/config.yaml is read at startup (Config.load); ship it (no secrets in it).
COPY config ./config

# Cloud Run sends traffic to $PORT (default 8080); the entrypoint honors it.
EXPOSE 8080
CMD ["python", "-m", "cop_thief.mcp_servers.cloud_entry"]
