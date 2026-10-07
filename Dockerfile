FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock ./
RUN python -m pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml README.md ./
COPY careergraph ./careergraph
COPY examples ./examples
COPY scripts/container-start.py ./scripts/container-start.py
RUN python -m pip install --no-cache-dir --no-deps . \
    && useradd --create-home --uid 10001 careergraph \
    && mkdir -p /app/data \
    && chown -R careergraph:careergraph /app
USER careergraph
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health',timeout=2)"
CMD ["python", "scripts/container-start.py"]
