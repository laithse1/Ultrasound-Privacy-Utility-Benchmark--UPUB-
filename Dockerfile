FROM python:3.11-slim@sha256:db3ff2e1800a8581e2c48a27c3995339d47bdf046da21c7627accd3d51053a93

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

COPY requirements-api.txt ./
RUN --mount=type=cache,target=/root/.cache/pip pip install -r requirements-api.txt
COPY pyproject.toml README.md ./
COPY src ./src
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000
CMD ["uvicorn", "us_privbench.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
