# ADR 0001 — Two volunteer bounded contexts (logistics dispatch vs. volunteer service)

Status: **Accepted** (2026-07-14)

## Context

Two services carry a `VolunteerProfile` model and volunteer-facing APIs:

| | Logistics (`/api/volunteers`) | Volunteer service (`/api/volunteer`) |
|---|---|---|
| Actor | **Tenant-registered** portal volunteers | **Global** mobile-app volunteers (`tenant_id = NULL` in IAM) |
| Owned data | availability enum, area, lat/lng, skills as rows | base_district, city, availability flag, skills as JSONB |
| Use case | Manual dispatch: a coordinator assigns one volunteer to one approved help request | Automated matching: district-resolved broadcast, FCFS quota acceptance, team formation |
| Identity source | `user_replicas` (event-carried from IAM) | replicated identity fields on the profile itself |

They look like a duplicated bounded context, and the API prefixes differ by
one letter. This ADR records why both exist and what the plan is.

## Decision

The two models describe **different aggregates for different actors**, not
one aggregate copied twice:

- The logistics module serves the *tenant-scoped dispatch* workflow — a human
  coordinator picking a known volunteer of that organization for a specific
  help request. Its invariants are tied to the help-request lifecycle
  (a task requires an APPROVED request).
- The volunteer service serves the *global disaster-response* pipeline — mobile
  volunteers who belong to no tenant, matched by district adjacency and skill
  quotas, fully event-driven. Its invariants (FCFS quota gate, one bucket per
  volunteer per event) do not exist in logistics.

Merging them would couple the help-request aggregate to the matching engine
and force one profile shape onto two different actor populations.

**However, the long-term ownership target is the volunteer service.** The
logistics volunteer module is frozen:

1. No new capabilities are added to `services/logistics/app/models/volunteer.py`
   or `routes_volunteers.py` (bug fixes only).
2. When tenant-scoped dispatch needs richer volunteer data, the volunteer
   service grows a tenant-affiliated profile and logistics consumes
   `volunteer.*` events instead — at that point `/api/volunteers` is retired
   with a deprecation window.
3. The route table comment in `gateway/app/core/config.py` marks the logistics
   prefix as legacy; this ADR is the authoritative statement.

## Consequences

- Reviewers should evaluate the two models against their own aggregate rules,
  not as accidental duplication.
- The near-miss prefixes (`/api/volunteers` vs `/api/volunteer`) remain until
  the deprecation completes; the gateway's longest-prefix routing
  distinguishes them correctly (`/api/volunteers/...` never matches
  `/api/volunteer`), and a routing test pins this behavior.
