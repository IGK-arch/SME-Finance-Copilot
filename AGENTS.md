# Project instructions: SME Finance Copilot

> **Orientation first:** read `CLAUDE.md` (project map, file responsibilities, invariants, how to run
> tests/servers on this machine, current status, what not to read). It is the single short source of
> truth for navigation; do not re-read MASTER_SPEC or the technical report unless the task needs it.
> The rules below are the original handoff instructions and still apply.

Этот файл — предлагаемые инструкции проекта. При наличии существующего AGENTS.md сначала согласуйте содержимое; не перезаписывайте его автоматически.

## Источник требований

`MASTER_SPEC.md` — консолидированная спецификация. R1–R3 — исходные документы с собственными статусами. Последние решения и реестр уточнений имеют приоритет над ранними идеями. Трек E выбран; блокчейн/Agent Wallet не входят в P0.

## Домен

Деньги — integer minor units + currency; ставки/округление явные. Invoice, obligation, predicted receipt, submitted payment и settlement различаются. Факты версионируются, observed time отделено от effective/event time. Не терять unmatched cash. Не дублировать merchant revenue и provider settlement.

## Безопасность

LLM только читает разрешённое, вызывает compute и предлагает действия. Реальные решения исполнителя — server-side authorization, approvals, актуальные preconditions, reserves, idempotency, outbox/inbox и reconciliation. Без банковских ключей в модели. Tenant isolation распространяется на API, БД, очереди, файлы и кэш. Kill switch не отменяет уже отправленные операции фиктивно.

## Режим разработки

По умолчанию synthetic data, sandbox execution, no real notifications, no unapproved egress. Не использовать платные сервисы/реальные деньги без разрешения. Mock LLM помечать как mock. Реальные модельные метрики получать отдельным запуском.

## Качество

Типы, ошибки, миграции, версия контрактов и тесты обязательны. Не подавлять исключения возвратом success. Нет фиктивных test results, хардкода итогового баланса под одну демонстрацию и доступа к скрытому будущему. Принцип: простое работающее безопасное ядро перед усложнением.

## Рабочий процесс

Сначала осмотр repo и план, затем реализация. Не разрушать существующие пользовательские изменения. Подтверждать состояние каждой итерации фактическими test commands/results. Помечать NOT_RUN, показывать ограничения, обновлять docs и traceability. Для непроверенной внешней интеграции — интерфейс и явный unsupported, а не выдуманное подключение.
