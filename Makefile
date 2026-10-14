PYTHON ?= python
.PHONY: setup up migrate seed-demo test test-integration test-security e2e test-live doctor demo benchmark report check down
setup:
	$(PYTHON) -m scripts.task setup
up:
	$(PYTHON) -m scripts.serve
migrate:
	$(PYTHON) -m scripts.task migrate
seed-demo:
	$(PYTHON) -m scripts.task seed-demo
test:
	$(PYTHON) -m scripts.test
test-integration:
	$(PYTHON) -m scripts.test --pattern test_postgres.py --output artifacts/postgres-tests.json
test-security:
	$(PYTHON) -m scripts.test --pattern test_execution.py --output artifacts/security-results.json
e2e:
	$(PYTHON) -m scripts.browser_evidence
test-live:
	$(PYTHON) -m scripts.doctor --live
doctor:
	$(PYTHON) -m scripts.doctor
demo:
	$(PYTHON) -m scripts.demo
benchmark:
	$(PYTHON) -m scripts.benchmark
report:
	$(PYTHON) -m scripts.report
check:
	$(PYTHON) -m scripts.check
down:
	$(PYTHON) -m scripts.task down
