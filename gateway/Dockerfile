# Build from the repository root so packages/ is reachable:
#   docker build -f gateway/Dockerfile .
FROM python:3.12-slim

WORKDIR /srv

COPY packages/common ./packages/common
COPY packages/clients ./packages/clients
COPY gateway/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt ./packages/common ./packages/clients

COPY gateway/app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
