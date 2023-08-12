FROM python:3.11.4-slim@sha256:7ad180fdf785219c4a23124e53745fbd683bd6e23d0885e3554aff59eddbc377

RUN apt-get update && \
    apt-get install -y libpq-dev gcc

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    APP_HOME=/app \
    PORT=1234

WORKDIR $APP_HOME
COPY . ./


RUN pip install --no-cache-dir -r requirements.txt

# As an example here we're running the web service with one worker on uvicorn.
CMD exec uvicorn local_server.main:app --host 0.0.0.0 --port ${PORT} --workers 2
