# ADR 0002 — Continue the existing financial kernel

Status: accepted for implementation, 2026-10-12.

The full-product instruction supersedes ADR 0001's milestone scope. Keep the
tested money, ingestion, authorization, execution and independent sandbox code.
Make normal startup persistent, then replace mock-only orchestration with
LangGraph checkpoints and a configurable local Ollama adapter. Mock remains an
explicit offline test mode. No live invocation without configuration and opt-in.
Replace the production planning entry point with OR-Tools CP-SAT; keep exact
enumeration as a small-space test oracle. Independent validation stays mandatory.

Use an isolated CPython .venv (the default MSYS interpreter cannot use Windows
native OR-Tools wheels). Pin the actual installed dependencies. LangSmith tracing
is disabled: no external traces or client data are authorized.

Retain the existing English browser application and progressively expose real
workspace routes. A frontend rewrite alone would not satisfy the request.
SQLite remains the local persistence backend until PostgreSQL migrations and
integration are implemented and exercised. PostgreSQL, RLS and deployment process
isolation must not be marked verified from SQLite tests. No PostgreSQL or Docker
executable was found in PATH or the usual Windows install locations in this audit.

Provider references verified before implementation:
- https://docs.langchain.com/oss/python/langgraph/persistence
- https://docs.langchain.com/oss/python/langgraph/interrupts
- https://developers.google.com/optimization/cp/cp_solver
- https://docs.ollama.com/api/chat

These are API documentation references, not model-quality or license claims.
