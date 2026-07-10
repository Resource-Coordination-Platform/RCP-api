# Docker image conventions

Each deployable owns its Dockerfile (independent deployability):

| Image | Dockerfile | Build context |
|---|---|---|
| gateway | `gateway/Dockerfile` | repo root |
| iam | `services/iam/Dockerfile` | repo root |
| logistics | `services/logistics/Dockerfile` | repo root |
| analytics | `services/analytics/Dockerfile` | repo root |
| rto | `services/rto/Dockerfile` | `services/rto` |

Python images build from the **repo root** so they can install
`packages/common` (and `packages/clients` for the gateway) without
duplicating shared code into each service:

```bash
docker build -f services/analytics/Dockerfile -t rcp/analytics .
```

The Go RTO image is self-contained and still builds from its own directory.

Local orchestration lives in `infra/compose/docker-compose.yml`
(+ `docker-compose.monitoring.yml` overlay); production images are pushed to
the registry managed by `infra/terraform/modules/container-registry`.
