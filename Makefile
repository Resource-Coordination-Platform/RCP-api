COMPOSE = docker compose -f infra/compose/docker-compose.yml

.PHONY: up down logs ps build check-python migrate-iam migrate-logistics

up:            ## start the full local stack (db, rabbitmq, all services)
	$(COMPOSE) up -d --build

down:          ## stop and remove containers (volumes persist)
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

check-python:  ## verify both FastAPI services' ORM mappings configure
	cd services/iam && python -c "import app.models; from sqlalchemy.orm import configure_mappers; configure_mappers(); print('iam OK')"
	cd services/logistics && python -c "import app.models; from sqlalchemy.orm import configure_mappers; configure_mappers(); print('logistics OK')"

migrate-iam:   ## generate + apply an IAM migration (AUTO_CREATE_TABLES=false in prod)
	cd services/iam && alembic revision --autogenerate -m "$(m)" && alembic upgrade head

migrate-logistics:
	cd services/logistics && alembic revision --autogenerate -m "$(m)" && alembic upgrade head
