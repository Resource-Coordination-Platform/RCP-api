python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt

# Start the shared local infrastructure first so Postgres is listening on 5432.
# From the repo root:
# docker compose -f infra/compose/docker-compose.yml up -d db rabbitmq

# Then run the migration from the service folder that owns the schema.
# For analytics, make sure DATABASE_URL points at the local db container or
# is loaded from .env before running:
# alembic upgrade head

