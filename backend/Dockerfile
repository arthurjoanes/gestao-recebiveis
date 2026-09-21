FROM ghcr.io/astral-sh/uv:0.9.18@sha256:5713fa8217f92b80223bc83aac7db36ec80a84437dbc0d04bbc659cae030d8c9 AS uv
FROM python:3.13.15-alpine3.24@sha256:79e7a9b9ff1cbceff819f856fb374477792a5967759d94df266de7b7b4120e6f AS dependencies
COPY --from=uv /uv /bin/uv
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv UV_LINK_MODE=copy uv sync --frozen --no-install-project --no-build

FROM python:3.13.15-alpine3.24@sha256:79e7a9b9ff1cbceff819f856fb374477792a5967759d94df266de7b7b4120e6f
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src \
    MYPY_CACHE_DIR=/tmp/gestao_recebiveis-mypy RUFF_CACHE_DIR=/tmp/gestao_recebiveis-ruff
WORKDIR /app
COPY --from=dependencies /app/.venv /app/.venv
COPY backend/ ./
COPY data/ /data/
COPY scripts/check-backend.sh /scripts/check-backend.sh
RUN addgroup -g 10001 gestao_recebiveis \
    && adduser -D -H -u 10001 -G gestao_recebiveis gestao_recebiveis \
    && chown -R gestao_recebiveis:gestao_recebiveis /app \
    && rm -rf /usr/local/lib/python3.13/site-packages/pip \
        /usr/local/lib/python3.13/site-packages/pip-*.dist-info \
        /usr/local/lib/python3.13/ensurepip \
    && rm -f /usr/local/bin/pip*
USER gestao_recebiveis
EXPOSE 8101
CMD ["uvicorn", "gestao_recebiveis.app:app", "--host", "0.0.0.0", "--port", "8101"]
