# Build from the repository root so packages/ is reachable:
#   docker build -f services/logistics/Dockerfile .
FROM python:3.12-slim

WORKDIR /srv

COPY packages/common ./packages/common
COPY services/logistics/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt ./packages/common

COPY services/logistics/app ./app
COPY services/logistics/migrations ./migrations
COPY services/logistics/alembic.ini .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
