# Deterministic mock model card

The application defaults to finance.gateway.ChatGateway in MOCK mode. Its fixed
sequence calls actual snapshot, metrics, forecast, product screening and planning
tools in the same persistent LangGraph used by the Ollama adapter. Test scripts can
inject clarification messages to exercise durable question/answer resume.

There are no learned weights, natural-language understanding or model-generated
financial balances. Domain functions perform all arithmetic; the independent
simulator evaluates actual results. Calls are counted; mock token value zero is
fixture accounting, not measured live usage. Billed cost is null. No real model
quality/latency/cost claim follows from these tests.

Legacy finance.agents.ModelGateway/workflow remains for compatibility/oracle tests;
the FastAPI workspace uses finance/workflows.py and finance/gateway.py. No failure
in a live provider silently becomes a mock success. See local-gateway.md for the
actual provider contract, egress policy, budgets and BLOCKED live-test status.
