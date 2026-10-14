# Следующая итерация Codex: надёжный агент и UX владельца бизнеса

Продолжи СУЩЕСТВУЮЩИЙ SME Finance Copilot v0.2.0. Не создавай новый проект рядом, не возвращайся к лендингу, не переписывай рабочую финансовую логику ради дизайна.

## Входные материалы

1. Текущий репозиторий и действующие AGENTS-инструкции.
2. TECHNICAL_REPORT_RU.md — отчёт, который нужно сверить с кодом и реальными артефактами.
3. AUDIT_AND_UX_SPEC_RU.md — приоритеты, уточнения архитектуры и acceptance V03-01…V03-25.
4. Исходный MASTER_SPEC, его контракты, I01–I36/T001–T100/W01–W36 и реестр уточнений.
5. UX_Prototype.html — автономный визуальный reference. Он НЕ подключён к backend и НЕ является заменой продукта. Не переносить из него фиктивные события/числа в API-связанный UI. Использовать композицию, названия, hierarchy и сценарии.

Сначала проверь доступность файлов. Не заявляй чтение недоступных материалов. Новые решения оформи ADR; старые требования/сырые результаты не переписывай ради зелёной матрицы.

## Цель

Пользователь заходит и без знания snapshot/worker/approval internals понимает:
- хватает ли денег;
- что и к какой дате требует решения;
- почему это происходит;
- какие допустимые варианты есть;
- что именно он подтверждает;
- что реально произошло после подтверждения.

Настоящий агент понимает поручение, использует реальные инструменты, даёт корректные суммы и источники, уточняет неизвестное и продолжает процесс. Он не должен заставлять ждать несколько минут простой уже вычисленный баланс, обещать действие без результата или подставлять snapshot_id вместо source_id.

## Не разрушать реализованное

Сохранить integer money, две временные оси, версии фактов/политик, allocations, real OR-Tools, independent validator, RLS/ACL, exact approvals, selected_action scope, reservations, stable idempotency, outbox/inbox, UNKNOWN, recovery, наблюдение и независимый sandbox/evaluator. Не обходить серверные проверки через новый UI. Не делать глобальное approve-all.

Сохранить synthetic/sandbox и opt-in модель. Реальные деньги/уведомления/новые внешние передачи данных/платные вызовы не разрешены этим поручением. Соблюдать прежние RAM/disk/commit floors и singleton launcher. Не завершать чужие приложения, не менять pagefile, не скачивать другие веса автоматически.

## Этап 0 — аудируемая точка старта

Осмотри код, tests, текущие процессы и workspace. Не seed/reset существующие данные. Создай безопасную согласованную backup/checkpoint стратегию перед миграциями; не делай вид, что копия живых SQLite-файлов без координации всегда консистентна.

Если Git metadata действительно нет, подготовь локальный репозиторий с безопасным .gitignore, проверь секреты и создай baseline commit согласно разрешениям среды. Никакого push/publication без разрешения. Если Git уже есть, не переинициализируй.

Запусти доступную полную regression, явно включив PostgreSQL config. SKIPPED/NOT_RUN не PASS. Исправь health backend label, обнови current-status docs, сохрани raw evidence. После последних изменений grader/launcher полная серия ранее не повторялась — не переносить старые 163 PASSED на новый код автоматически.

Выполни browser walkthrough всех десяти текущих разделов: screenshots, основные клики, pain points, console/network errors. Только после этого формулируй визуальные дефекты текущего UI.

## Этап 1 — контракт ответа и короткий путь агента

- Добавь TaskSpec и CompletionGate. Проверяй необходимые результаты, не фиксированную последовательность вызовов. Уже авторизованный snapshot может быть достаточен для простого cash-вопроса.
- Добавь бизнес-навыки поверх существующего домена: cash status, explain gap, funding comparison, inspect obligation, scenario, prepare selected action.
- Сохрани гибкий tool loop для неоднозначных/исследовательских запросов. Не своди весь продукт к canned responses и не добавляй множество декоративных агентов.
- Отдавай узкий релевантный набор tools и компактные object summaries; создай серверные aggregation/filter/cursor API вместо перебора пятирядных страниц и разорванного JSON.
- Сохрани visible-ID/tenant/role checks. Короткие handles разрешаются сервером только в текущем scope; никаких approximate IDs.
- AnswerBundle использует typed metrics/calculations/evidence. Суммы, currency, dates и refs рендерит сервер из реального результата. Свободный текст не считается финансовым доказательством.
- Покажи завершённые вычисления до завершения narrative. При timeout объяснения computation остаётся доступным, но workflow/test status не переписывается как полный успех.
- Добавь latency telemetry по model load/prefill/generation/tools/queue; cold/warm отдельно. Параметры провайдера сверяй с pinned runtime.
- LIVE error не становится mock success. Новая модель/digest требует разрешённого нового связанного workflow, а не тайной смены посередине.

## Этап 2 — UX одной задачи, а не десяти технических модулей

Сначала реализуй связанный ключевой путь, затем остальные экраны. Предлагаемая навигация:
Home / Money / Plans / Documents / Activity; Settings отдельно; Copilot — глобальная контекстная панель.

Введи FinancialCase/read model, объединяющий проблему, snapshot, сценарии, варианты, вопросы, выбранные действия и evidence. Не дублируй ledger или solver.

Home: один основной alert/next action, 3–4 понятные метрики, прогноз с reserve и zero, ближайшие обязательства. Различай empty, data review, gap, pending approval, calculating, unknown payment, no detected gap.

Plans: действительное сравнение financing/no new debt/conditional extension; область проверенных сценариев, net/gross/fees/repayment, поздняя выдача и failed stress. Не рисуй три одинаковые рекомендации. Неподтверждённая отсрочка не executable.

Approval: человеческое описание exact payload, получатель/сумма/валюта/условия/последствия; raw hashes под details. После подтверждения — фактическая timeline; UNKNOWN не имеет кнопки blind repayment. Выбор одного action не запускает все остальные.

Documents: upload → column mapping → preview → errors/review → commit. Хотя бы flexible CSV/XLSX для transactions и obligations. Decimal и dates разбираются сервером; исходные файлы и corrections прослеживаются. Не заявляй банковский adapter по generic upload.

Copilot: открытый case/plan/invoice в контексте, короткий ответ + result card + evidence + next action; реальные stage events, история и resume. Не показывай fake chain of thought или fake percentage progress.

Session: безопасное сохранение входа на refresh, server-side expiry/revocation, role enforcement, no bearer in localStorage. Для HTTPS deployment HttpOnly/Secure/SameSite + CSRF protection; loopback dev отдельно. Не подменяй auth скрытым OWNER-входом.

Дизайн: светлый рабочий fintech, единые tokens/components, хороший CNY typography и CJK fallback; не cosmetic reskin прежних технических форм. React не обязателен: реши по коду, нужен ли постепенный перенос на типизированные компоненты. Никакого big-bang rewrite backend.

## Этап 3 — финансовые и событийные недочёты

- Реализуй либо честно убери отдельную стратегию PRESERVE_LIQUIDITY, сейчас равную MIN_COST.
- Для HIGHER_RESERVE определи target/price tradeoff, чтобы не поощрять неограниченное заимствование ради лишнего cash.
- Выводи grid/candidate scope, solver status, required versus optional stress scenarios и конкретные причины infeasible.
- Создай внутренний alerts/cases workflow с dedup/debounce по фактам; без реальных уведомлений. Завершение alert не равно выбору плана.
- Дай what-if по выбранному контрагенту/обязательству, сохрани immutable actual data.
- Проверь реальные часы TTL approval, бесконечную инвалидизацию нерелевантными updates, повтор BALANCE, int64→JS loss, shared API/worker grants, parser memory и private world isolation. Это вопросы аудита: сначала воспроизведи/проверь, не объявляй найденную уязвимость без доказательства.
- Новые финансовые возможности — только с независимым validator/oracle; не симулируй универсальный planner фронтендом.

## Этап 4 — обязательные доказательства

Восстанови полный путь через браузер с настоящими API/БД/worker/sandbox. Golden direct prepare/deliver остаётся полезным отдельным тестом, но не заменяет этот прогон.

1. Человек загружает или меняет наблюдаемые данные.
2. Backend пересчитывает проблему, интерфейс отражает её.
3. LIVE-агент делает задачу по новым данным либо корректно задаёт вопрос.
4. Пользователь выбирает реальный вариант и подтверждает ровно выбранное действие.
5. Queue worker исполняет, sandbox даёт наблюдение, reconciliation фиксирует результат.
6. При lost response нет двойного платежа; после рестарта состояние продолжается.
7. UI показывает конечное состояние и проверяемые основания.

Нужны Playwright runner, trace, screenshots, API/domain assertions, raw model events, independent world result. Не подменять backend сеть route.fulfill в этом golden-тесте. Отдельные mock browser tests допустимы и маркируются.

Сохрани прежние LIVE 20 кейсов/градер для сопоставимости, добавь авторизованные execution-задачи и заранее закрытый holdout. Не заявляй надёжность по одним отказам: серия без единого action не подтверждает правильную оплату. Не маскируй отсутствие ключа/ресурсов/внешнего разрешения: LIVE NOT_RUN и отдельные детерминированные доказательства.

Протестируй 1440×900, 1366×768, 768×1024, 390×844; keyboard, focus, 200% zoom; длинный китайский текст, плохие данные, timeout, stale approval и UNKNOWN. Проверяй реальный смысл и действия, не только изображения. Trace может содержать токены — хранить приватно и проверять утечки.

## Порядок выполнения и отчёт

Создай план по V03-* с зависимостями и короткими вертикальными этапами. После короткого аудита начни код в этой же сессии. Не заканчивай только новым планом или созданием компонентов без подключения.

Каждая итерация: что изменено, какие V03/T покрыты, файлы, команды/результаты/доказательства, что не проверено, следующий шаг. При лимите сессии сохрани checkpoint продолжения без обещания фоновой работы. Статусы: MISSING/PARTIAL/IMPLEMENTED_UNVERIFIED/VERIFIED/BLOCKED.

Финальная цель: владелец способен пройти задачу, а система даёт корректный финансовый результат. Число страниц, классов, tools и зелёный frontend build — не критерий готовности.
