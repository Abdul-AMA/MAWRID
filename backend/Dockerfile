# syntax=docker/dockerfile:1
FROM python:3.11-slim

RUN apt-get update && apt-get install -y \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements-api.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --retries 5 --timeout 120 -r requirements-api.txt

COPY . .

EXPOSE 8000
