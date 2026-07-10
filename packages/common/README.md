# rcp-common

Shared Python utilities for RCP services. Owns exactly the code that would
otherwise be vendored per service:

- `rcp_common.logging` — JSON structured logging (`configure_logging`)
- `rcp_common.middleware` — `RequestContextMiddleware` (X-Request-ID + access log)
- `rcp_common.exceptions` — shared error hierarchy
- `rcp_common.config` — `BaseServiceSettings` (service name, environment, log level)
- `rcp_common.auth` — JWKS verification of IAM-issued RS256 JWTs +
  FastAPI dependencies (`PrincipalDependency`, `require_any_role`)

## Install

Local development (from repo root):

```bash
pip install -e packages/common
```

In service Dockerfiles the package is copied and installed from the repo-root
build context (see any `services/*/Dockerfile`).

No business logic belongs here — bounded-context rules live in their service.
