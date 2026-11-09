FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY common ./common
COPY services ./services
COPY scripts ./scripts
RUN useradd --create-home appuser
USER appuser
ENV PYTHONPATH=/app SECRETS_DIR=/run/secrets
# El módulo se define por servicio en docker-compose.yml (APP_MODULE)
CMD ["sh", "-c", "uvicorn $APP_MODULE --host 0.0.0.0 --port 8000 --no-access-log"]
