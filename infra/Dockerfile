FROM ghcr.io/astral-sh/uv:0.13.1 AS uv
FROM node:24.19.0-bookworm-slim AS node

FROM python:3.11.9-slim-bookworm AS api
WORKDIR /app
COPY --from=uv /uv /usr/local/bin/uv
ENV UV_PYTHON_DOWNLOADS=never PATH="/app/.venv/bin:$PATH"
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev
COPY services services
COPY scripts scripts
COPY data data
CMD ["uvicorn", "app.main:app", "--app-dir", "services/api", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]

FROM node AS web
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1 API_INTERNAL_URL=http://127.0.0.1:8000
COPY package.json package-lock.json ./
COPY apps/web/package.json apps/web/package.json
RUN npm ci --no-audit --no-fund
COPY apps/web apps/web
RUN npm run build:web
WORKDIR /app/apps/web
USER node
CMD ["node", "/app/node_modules/next/dist/bin/next", "start", "--hostname", "0.0.0.0", "--port", "3000"]

FROM api AS qa
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s /usr/local/lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s /usr/local/lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx
COPY . .
ENV NEXT_TELEMETRY_DISABLED=1
RUN uv sync --locked && npm ci --no-audit --no-fund && npx playwright install --with-deps chromium
