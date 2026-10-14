# Контекст среды для Codex

Заполнить известные поля; неизвестные оставить NOT_CONFIGURED. Здесь не должно быть ключей, паролей и реальных клиентских данных. Этот файл — информация для исполнителя, а не готовая конфигурация приложения. Имена переменных согласовать с существующим кодом.

```text
PROJECT_ROOT = путь к реальному репозиторию
HANDOFF_PATH = путь к распакованному sme_codex_handoff
CURRENT_STATE = кратко, что уже создано; фактическую готовность проверить аудитом
RUN_ENVIRONMENT = Windows / WSL / Linux / macOS / remote
DOCKER_AVAILABLE = yes / no / unknown
GPU = CPU_ONLY или доступная GPU и память

DATA_MODE = synthetic
EXECUTION_BACKEND = sandbox
ALLOW_REAL_FINANCIAL_ACTIONS = false
ALLOW_EXTERNAL_NOTIFICATIONS = false
ALLOW_UNAPPROVED_DATA_EGRESS = false

MODEL_PROVIDER = NOT_CONFIGURED или выбранный реальный provider
MODEL_NAME = NOT_CONFIGURED или подтверждённый идентификатор модели
MODEL_BASE_URL = NOT_CONFIGURED или разрешённый endpoint
MODEL_API_KEY_ENV_NAME = имя переменной, из которой приложение получит ключ; НЕ значение ключа
ALLOW_PAID_LLM_CALLS = false до явного разрешения
APPROVED_LLM_TEST_BUDGET = NOT_APPROVED или сумма и валюта
APPROVED_MODEL_EGRESS = none либо только synthetic data в перечисленный разрешённый endpoint
ALLOW_MODEL_WEIGHT_DOWNLOAD = false до согласования размера/лицензии
ALLOW_PUBLIC_DEPLOYMENT = false до отдельного разрешения

PRODUCT_LANGUAGE = English; поддержка китайских данных/документов
ARCHITECTURE = MASTER_SPEC.md; изменения через ADR
TARGET_SCOPE = полный P0 + продуктовые/агентные возможности P1; P2 отдельно
```

Если реальный LLM ещё не выбран: реализовать provider adapter, валидируемую конфигурацию, реальный граф и offline-тесты; в UI показать AI not configured. Live-проверку не считать пройденной. Наличие ключа само по себе не является разрешением на неопределённые расходы или реальное финансовое исполнение.

## Короткое поручение для следующей сессии

```text
Продолжай SME Finance Copilot по CODEX_BUILD_FULL_PRODUCT.md и MASTER_SPEC.md. Сначала прочитай docs/IMPLEMENTATION_STATUS.md, docs/IMPLEMENTATION_PLAN.md и docs/ACCEPTANCE_MATRIX.md, затем проверь фактический код и тесты. Не начинай проект заново и не ограничивайся редизайном. Выбери следующий незавершённый этап P0/P1, реализуй его end-to-end, выполни доступные проверки и обнови evidence. Статус live-модели указывай отдельно от sandbox-исполнения. При блокере зафиксируй его и продолжай независимые части. Заверши отчётом о реальных изменениях, командах, результатах и точке продолжения, не выдавая промежуточную работу за готовый продукт.
```
