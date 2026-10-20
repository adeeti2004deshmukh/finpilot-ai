FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

WORKDIR /workspace
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY alembic ./alembic
COPY alembic.ini seed.py ./
COPY scripts ./scripts
RUN useradd --create-home --uid 10001 finpilot && chown -R finpilot:finpilot /workspace
USER finpilot

EXPOSE 8000
CMD ["python", "-m", "app.serve"]
