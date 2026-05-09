FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY pyproject.toml ./
COPY src/ ./src/

# Install dependencies (no dev extras)
RUN uv pip install --system --no-cache .

# Runtime
EXPOSE 8080
CMD ["uvicorn", "poc_cesg_poi_search.app:app", "--host", "0.0.0.0", "--port", "8080"]
