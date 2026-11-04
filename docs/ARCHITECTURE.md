# YoYo Dev — Architecture

```
src/yoyo/
├── domain/           pure business rules, no I/O, no framework imports
│   ├── agent.py          YoYoAgent — aggregate root (tasks, tricks, points, tick state machine)
│   ├── value_objects.py  Progress, TaskLabel, BonusPoints, Trick, enums (self-validating, immutable)
│   ├── events.py         AgentStateChanged, TrickPerformed, NotificationRaised, ...
│   ├── errors.py         DomainError hierarchy
│   └── repositories.py   AgentRepository (port)
├── application/      use cases; depends only on domain + ports
│   ├── ports.py          Clock, EventBus, UnitOfWork (abstractions)
│   ├── services.py       GameCommandService (write) / GameQueryService (read + cache)
│   ├── commands.py       input messages          dto.py  read models
│   ├── mappers.py        domain -> DTO -> wire   cache.py  TTL cache
│   └── event_bus.py      in-process pub/sub
├── infrastructure/   adapters (the only layer that knows about the outside world)
│   ├── memory.py         in-memory repository + Unit of Work
│   ├── ws_hub.py         WebSocket fan-out     subscribers.py  event handlers
│   └── clock.py, worker.py
├── api/              FastAPI: schemas.py (boundary validation) + app.py (thin routes)
├── container.py      composition root (Dependency Injection)
└── settings.py
```

Dependency rule: `api → application → domain`, and `infrastructure → application/domain`.
Nothing in `domain` or `application` imports FastAPI, asyncio primitives for I/O, or a concrete adapter.

## Where each concept lives

| Concept | Where |
|---|---|
| **Clean Architecture / DDD** | layers above; `YoYoAgent` is the aggregate root, `Progress`/`TaskLabel`/`BonusPoints` are value objects, `AgentRepository` is a domain-owned port |
| **Event-driven design** | aggregate raises events → `UnitOfWork.events` → `EventBus` (published *after* commit) → `WebSocketBroadcaster`, `CacheInvalidator` |
| **SOLID** | S: one reason to change per module · O: new reaction = new handler + one `subscribe` line · L: `InMemoryUnitOfWork` is substitutable for any `UnitOfWork` · I: small ports (`Clock`, `EventBus`, `UnitOfWork`) · D: services depend on ports, wired in `container.py` |
| **Dependency Injection** | constructor injection everywhere; `build_container(settings, clock, rng)` — tests pass a fake clock and seeded RNG; FastAPI routes get the container via `Depends` |
| **Repository + Unit of Work** | `uow.agents.get()/save()`; the in-memory UoW hands out copies and holds a lock for the transaction, so failures roll back and writes are serialized (`tests/test_unit_of_work.py`) |
| **Object mapping / model separation** | pydantic request schema → command → domain aggregate → DTO → wire dict; each arrow is one function (`api/schemas.py`, `application/mappers.py`) |
| **Validation** | two levels: *shape* at the boundary (pydantic: types, lengths, ranges → HTTP 422) and *business rules* in the domain (cooldown → 429, nothing to complete → 409, unknown trick → 422) |
| **Caching** | `GameQueryService` caches state/stats for 1 s; every domain event invalidates it (subscribed first, so broadcasts read fresh data) |

## Distributed-systems trade-offs

The system is three cooperating processes: the **game server**, the **MCP server** (spawned by Claude), and
the **window tracker**, plus Claude Code **hooks**. They talk over HTTP/WebSocket.

* **Availability over consistency for telemetry.** The game is decorative; Claude's real work must never wait on it.
  The MCP gateway uses a 2 s timeout, never raises, and after a failure backs off for 8 s (a minimal circuit breaker).
  Tool results tell Claude to simply continue. Hooks swallow every error and always exit 0.
* **At-most-once, best-effort delivery.** WebSocket messages are not acknowledged or replayed. A client that
  reconnects receives a full snapshot (`agent_state`), so state converges without a message log.
* **Liveness via lease/TTL instead of explicit shutdown.** If Claude crashes mid-task, nobody sends `DONE`.
  An external task that has not been refreshed for `YOYO_TASK_TTL` seconds (default 90) is dropped by the tick
  state machine — a lease, the usual answer to "partial failure: you can't tell dead from slow".
* **Single-writer consistency inside the server.** One aggregate + one lock = linearizable writes without a
  distributed protocol. The price is that the server is a single instance. Scaling out (Railway replicas) would
  need shared storage (Redis/Postgres adapter behind the same ports) and a pub/sub backplane for WebSocket
  fan-out; the ports were drawn exactly where those swaps would happen.
* **Events after commit, not an outbox.** Publishing in-process after commit can lose events if the process dies
  between the two. Acceptable for UI notifications; for anything that must not be lost an outbox table
  written in the same transaction would be needed.
* **Read/write split (light CQRS).** Writes go through the aggregate; reads use cached DTOs. Staleness is
  bounded by the cache TTL and by invalidation on every event.

## How Claude is connected

1. **MCP server** (`src/mcp_server.py`, registered in `.mcp.json`): Claude gets tools `update_task`, `notify`,
   `get_status`, ... and server `instructions` explaining that the user is playing while it works.
   `get_status` reports `player_present` — true when the tracker sees the YoYo window in the foreground.
2. **Hooks** (`hooks/claude_hook.py`, registered in `.claude/settings.json`): mirror Claude Code activity
   (prompt → tool calls → stop) into the game with no cooperation from the model. Only tool names and file
   basenames are sent.
3. **Autostart**: with `YOYO_AUTOSTART=1` the MCP server launches the game the first time Claude reports
   something while it is down.
