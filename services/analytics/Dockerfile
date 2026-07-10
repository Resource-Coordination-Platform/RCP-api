# Build from the repository root so packages/ is reachable:
#   docker build -f services/analytics/Dockerfile .
FROM python:3.12-slim

WORKDIR /srv

COPY packages/common ./packages/common
COPY services/analytics/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt ./packages/common

COPY services/analytics/app ./app
COPY services/analytics/migrations ./migrations
COPY services/analytics/alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
