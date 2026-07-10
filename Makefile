COMPOSE = docker compose -f infra/compose/docker-compose.yml
COMPOSE_MON = $(COMPOSE) -f infra/compose/docker-compose.monitoring.yml

.PHONY: up up-monitoring down logs ps build check-python install-packages \
        migrate-iam migrate-logistics migrate-analytics

up:            ## start the full local stack (db, rabbitmq, gateway, all services)
	$(COMPOSE) up -d --build

up-monitoring: ## same, plus prometheus (:9090) and grafana (:3001)
	$(COMPOSE_MON) up -d --build

down:          ## stop and remove containers (volumes persist)
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

build:
	$(COMPOSE) build

install-packages: ## editable installs of the shared packages for local dev
	pip install -e packages/common -e packages/clients

check-python:  ## verify the FastAPI services' ORM mappings configure
	cd services/iam && python -c "import app.models; from sqlalchemy.orm import configure_mappers; configure_mappers(); print('iam OK')"
	cd services/logistics && python -c "import app.models; from sqlalchemy.orm import configure_mappers; configure_mappers(); print('logistics OK')"
	cd services/analytics && python -c "import app.models; from sqlalchemy.orm import configure_mappers; configure_mappers(); print('analytics OK')"

migrate-iam:   ## generate + apply an IAM migration (AUTO_CREATE_TABLES=false in prod)
	cd services/iam && alembic revision --autogenerate -m "$(m)" && alembic upgrade head

migrate-logistics:
	cd services/logistics && alembic revision --autogenerate -m "$(m)" && alembic upgrade head

migrate-analytics:
	cd services/analytics && alembic revision --autogenerate -m "$(m)" && alembic upgrade head
