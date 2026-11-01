FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app app
# Stdio MCP server: stdin/stdout are the transport, so no port is exposed.
# Run it attached: docker compose run --rm hive-mind
CMD ["python", "-m", "app.mcp_server", "--stdio"]
