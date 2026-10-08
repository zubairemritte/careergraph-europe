FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
RUN python -m pip install --no-cache-dir poetry==2.5.1
COPY pyproject.toml poetry.lock poetry.toml README.md ./
RUN poetry sync --only main --no-root --no-interaction
COPY careergraph ./careergraph
COPY examples ./examples
COPY scripts/container-start.py ./scripts/container-start.py
RUN poetry sync --only main --no-interaction \
    && useradd --create-home --uid 10001 careergraph \
    && mkdir -p /app/data \
    && chown -R careergraph:careergraph /app
USER careergraph
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2)"
CMD ["python", "scripts/container-start.py"]
