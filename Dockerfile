FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY requirements.lock .
RUN pip install --no-cache-dir -r requirements.lock && useradd --uid 10001 --create-home aaaem
COPY backend ./backend
COPY web ./web
COPY agents ./agents
COPY scripts ./scripts
COPY config ./config
COPY templates ./templates
COPY docs ./docs
RUN mkdir -p /app/.data && chown -R aaaem:aaaem /app
USER aaaem
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/healthz', timeout=3)"
CMD ["python", "scripts/serve.py", "--host", "0.0.0.0", "--port", "8000"]
