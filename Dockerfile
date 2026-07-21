FROM node:22.22.0-bookworm-slim@sha256:dd9d21971ec4395903fa6143c2b9267d048ae01ca6d3ea96f16cb30df6187d94 AS frontend

WORKDIR /frontend

COPY package.json package-lock.json ./
RUN npm ci --omit=dev --ignore-scripts --no-audit --no-fund \
    && mkdir -p /frontend/public \
    && cp -R node_modules/@hexlet/project-devops-deploy-crud-frontend/dist/. /frontend/public/

FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c AS builder

WORKDIR /app

RUN python -m pip install --no-cache-dir uv==0.11.29

COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev

FROM python:3.12.12-slim-bookworm@sha256:593bd06efe90efa80dc4eee3948be7c0fde4134606dd40d8dd8dbcade98e669c

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update \
    && apt-get install --yes --no-install-recommends gosu nginx \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --uid 10001 app

WORKDIR /app

COPY nginx.conf /etc/nginx/nginx.conf
RUN nginx -t

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=frontend --chown=app:app /frontend/public /app/public
COPY --chown=app:app main.py api.py database.py link_repository.py models.py ./
COPY --chmod=0755 docker-entrypoint.sh /usr/local/bin/start-app

EXPOSE 80

CMD ["start-app"]
