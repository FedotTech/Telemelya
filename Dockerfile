# Stage 1: Build
FROM python:3.12-slim AS builder

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

COPY pyproject.toml .
COPY telemelya/ telemelya/
RUN pip install --no-cache-dir --prefix=/install .

# Stage 2: Runtime
FROM python:3.12-slim

WORKDIR /app

COPY --from=builder /install /usr/local

COPY telemelya/ telemelya/

EXPOSE 8080

CMD ["python", "-m", "telemelya.server.app"]
