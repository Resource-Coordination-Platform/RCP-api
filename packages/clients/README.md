# rcp-clients

Typed HTTP clients for calling RCP services. Used by the API gateway (health
aggregation, request forwarding helpers) and by any service needing a
synchronous request/response call to a peer. Event-driven flows should use
the RabbitMQ contracts in `packages/contracts` instead.

```bash
pip install -e packages/clients
```
