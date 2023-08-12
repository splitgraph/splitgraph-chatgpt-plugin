FROM python:3.11.4-slim@sha256:7ad180fdf785219c4a23124e53745fbd683bd6e23d0885e3554aff59eddbc377

# required for psychopg2
RUN apt-get update && \
    apt-get install -y libpq-dev gcc

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    # HTTP port to listen to.
    PORT=3333 \
    # Postgres connection string.
    # use postgresql://username:XXX@host/db for normal postgres connections,
    # or use the default value below for cloudsql without auth proxy
    PG_CONN_STR=postgresql+pg8000:// \
    # CloudSQL connection variables. Safe to ignore if connecting to a regular
    # postgres db with the full connection string in $PG_CONN_STR
    INSTANCE_CONNECTION_NAME=NONE \
    DB_USER=NONE \
    DB_PASS=NONE \
    DB_NAME=NONE \
    PRIVATE_IP=0

WORKDIR $APP_HOME
COPY . ./


RUN pip install --no-cache-dir -r requirements.txt

# As an example here we're running the web service with 2 workers on uvicorn.
CMD exec uvicorn local_server.main:app --host 0.0.0.0 --port ${PORT} --workers 2
