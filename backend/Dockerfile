FROM ghcr.io/astral-sh/uv:0.9.18 AS uv
FROM python:3.13.12-slim-bookworm
COPY --from=uv /uv /uvx /bin/
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    UV_LINK_MODE=copy UV_COMPILE_BYTECODE=1 \
    PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app/src \
    MYPY_CACHE_DIR=/tmp/gestao_recebiveis-mypy RUFF_CACHE_DIR=/tmp/gestao_recebiveis-ruff
WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-install-project
COPY backend/ ./
COPY data/ /data/
COPY scripts/check-backend.sh /scripts/check-backend.sh
RUN useradd --create-home --uid 10001 gestao_recebiveis && chown -R gestao_recebiveis:gestao_recebiveis /app
USER gestao_recebiveis
EXPOSE 8101
CMD ["uvicorn", "gestao_recebiveis.app:app", "--host", "0.0.0.0", "--port", "8101"]
