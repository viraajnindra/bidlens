FROM python:3.12-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
COPY requirements.lock pyproject.toml ./
COPY backend ./backend
COPY data/demo.json ./data/demo.json
RUN pip install -r requirements.lock && pip install --no-deps -e .
COPY scripts ./scripts
RUN mkdir -p /app/data/runtime /app/data/sources
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
