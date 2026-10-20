# Business health в инструментах агента — 19 октября 2026

**Статус: интеграция выполнена; все 20 LIVE-сценариев завершены.** AUD-05 / OPEN-11 закрыт в части доступа к Business health через инструменты. На выбранной Qwen: **14/20 автоматических PASS**, но после просмотра всех ответов **11 COMPLETE / 2 PARTIAL / 7 FAILED**. Качество свободной прозы остаётся ограничением OPEN-12. Это дополнение к [техотчёту](TECHNICAL_REPORT_RU.md); исходные неуспехи сохранены.

## Реализация

Раньше кабинет Money вызывал `compute.analysis`, а `calculate_business_metrics` возвращал только базовые денежные итоги. Теперь модель получает те же детерминированные Business health расчёты; арифметика остаётся на сервере.

| Файлы | Изменение |
|---|---|
| `finance/compute.py` | Общий расчёт `analysis-v2`, типизированная проекция `business-health-v1`, включение в `metrics`; точная совокупная доля крупнейших контрагентов и число наблюдённых settled-транзакций |
| `finance/agents.py` | Business health в `calculate_business_metrics`, `forecast_cashflow`, `what_if_cashflow`; существующие сохранение полного расчёта и кэш с проверкой полномочий |
| `finance/agent_data.py` | `agent-tools-v5`; описание покрытия Business health через `get_platform_capabilities`; действующие scoped read/list доступны для сохранённых результатов |
| `finance/workflows.py`, `finance/answers.py` | Описания tools, правила выбора расчёта и трактовки данных; health в проекции ответа модели; уменьшение повторяющихся служебных полей; инструкция краткого ответа без цифровой нумерации, со ссылками на значения |
| `finance/copilot.py` | Карточка Business health с серверными суммами, процентами, сроками и возрастными группами; поддержка старых карточек без health |
| `contracts/business-health.schema.json`, `contracts/RUNTIME.md` | Версионированный контракт и границы значений |
| `scripts/business_health_scenarios.py`, `scripts/business_health_eval.py` | Отдельные 20 синтетических EN/ZH сценариев, fixtures, строгий grader, неизменяемые первичные исходы, контроль модели/ресурсов/хэшей |
| `tests/test_business_health_tools.py`, `tests/test_business_health_eval.py` | 17 новых тестов интеграции, прав, единиц, истории, сценариев, проекции и оценщика |

Поток: `get_financial_snapshot` → реальный разрешённый `snapshot_id` → compute tool → полный `agent_calculation` → ограниченная проекция для модели → ссылки на точные значения → текст и серверная карточка. По `result_id` доступны `list_business_records` / `read_business_record` на dataset `calculations`, с обычной пагинацией. Результаты остаются привязаны к snapshot, источникам, наблюдаемому времени и версии контракта.

Основной инструмент здоровья — `calculate_business_metrics`. `forecast_cashflow` включает здоровье базового сценария; `what_if_cashflow` — здоровье явно заданного сценария под `forecast.business_health`. `stress_test_plan` сохраняет отдельный смысл проверки уже сохранённого плана; его не подменяют произвольным hypothetical plan. Чтение snapshot само по себе не считается выполненным расчётом.

## Смысл и единицы

- **Net working position:** confirmed cash + открытые receivables − открытые payables. Это не прибыль и не полный бухгалтерский баланс.
- **Liquidity buffer:** минимум прогнозного остатка в указанном сценарии минус обязательный резерв. Отрицательное значение показывает прогнозный недостаток; это не текущий доступный остаток.
- **Days to gap:** полные дни до первого нарушения резерва. Ноль — нарушение уже сейчас; `null` — нет разрыва в данном горизонте, не бесконечный срок жизни бизнеса.
- **Coverage:** confirmed cash / просроченные и попадающие в ближайшую тридцатидневную группу payables. Значение в basis points, округление вниз. Нулевой знаменатель даёт `null` / `NOT_APPLICABLE`, не бесконечность.
- **Ageing:** пять групп по оставшимся полным дням до договорной даты платежа: overdue, d0_30, d31_60, d61_90, d90_plus. Последняя означает более девяноста дней. Деньги передаются через `outstanding_minor`, не безразмерные счётчики.
- **Concentration:** доля в открытых receivables/payables, не в выручке/расходах. `supplier_concentration` — историческое имя поля всех получателей исходящих обязательств, включая зарплату, аренду и кредитора. Совокупная доля top-three считается от сумм до округления, а не суммой округлённых процентов. При пустом знаменателе доля отсутствует.
- **Settled cashflow:** только наблюдённые `SETTLED` движения в интервале `(as_of − 30 дней, as_of]`. Число транзакций и входящий/исходящий поток отделены от invoices/submissions, доходов, расходов и прибыли. Ноль наблюдённых движений не означает, что модель располагает полной историей реального бизнеса.

В what-if меняются прогнозные buffer/gap, но текущие cash, net working position, ageing и concentration не превращаются в гипотетические факты учёта. `forecast_scope` содержит сценарий, delay/fraction и конец именно его горизонта. P&L остаётся `INSUFFICIENT_DATA`; credit score и калиброванная вероятность банкротства не вычисляются. Все суммы — integer minor units CNY, итоговые проценты и деньги подставляются серверным answer renderer.

Контракты: `agent-tools-v5`, `compute-v3`, `analysis-v2`, `business-health-v1`. Старые базовые поля сохранены; старые persisted calculations не переписываются. Новых таблиц или DDL-миграции нет. [ADR 0007](adr/0007-agent-business-health.md).

## Защита

Не добавлено инструментов подтверждения, отправки денег, SQL, shell или изменения политик. Разрешён только прежний READ/COMPUTE/PROPOSE. Владение snapshot и result ID, tenant isolation, текущие membership/role, повторная проверка прав перед выдачей кэша, bounded pagination и документные ACL сохраняются. Здоровый показатель не заменяет точное OWNER approval, payload hash или актуальные предусловия исполнения.

Предыдущее исправление [K15](SETTLEMENT_FIX_20261019_RU.md) сохраняется. Его execution/worker/approval-границы этим изменением не редактируются. Пользовательская PostgreSQL-база и действующие финансовые данные не менялись. Все модельные запросы используют отдельно созданные синтетические компании.

## Офлайн-проверки

Первые 12 тестов выявили ошибку новой проекции: в базовом forecast receipt fraction задан неявно. Это исправлено использованием существующей семантики полного поступления; финансовая модель не менялась. [Первая попытка](../artifacts/business-health-20261019/targeted-first.json): 2 PASS / 10 FAIL. [После исправления](../artifacts/business-health-20261019/targeted-core.json): 12/12 PASS. [С fixtures и grader](../artifacts/business-health-20261019/targeted-all.json): **15/15 PASS**. Все исходные файлы сохранены.

Тесты проверяют совпадение с кабинетом и заранее известными значениями; CNY/percentage references; отличие current от what-if; пустые знаменатели; отрицательный cash и нулевой срок разрыва; полные сохранённые результаты; исторический snapshot после исправления исходных данных; чужие IDs; отзыв membership после заполнения кэша; отказ неизвестному snapshot и лишним authority-полям; карточку/capabilities; округление концентрации до/после агрегации. Десять пар EN/ZH имеют идентичные финансовые условия; fixtures проверены без вызовов LLM.

После уточнений проекции и инструкции ответа целевой набор расширен до **17/17 PASS** ([итог](../artifacts/business-health-20261019/targeted-final.json)). Полная регрессия — **328 PASS / 4 PostgreSQL SKIP / 0 FAIL**, всего 332 теста ([итог](../artifacts/business-health-20261019/regression-final.json)). T001–T100: **95 PASS / 5 NOT_RUN** (T023, T031, T032, T094, T097). V03: 9 PASS / 3 PARTIAL / 5 NOT_RUN / 6 DEFERRED_MODEL / 2 EVIDENCE_RECORDED. Эти статусы не повышаются только на основании новой health-серии.

Свежий HTTP E2E — **23/23 PASS**, MOCK; [артефакт](../artifacts/business-health-20261019/e2e-final.json). `scripts.check` — **9/9 PASS**; [артефакт](../artifacts/business-health-20261019/quality-final.json). Канонический исторический quality JSON после запуска восстановлен, новая копия лежит в датированной папке. Дополнительный mypy тестового файла нашёл отсутствие явного narrowing для опциональной карточки; добавлен `assert card is not None` только в тест, затем целевые **17/17** повторены ([артефакт](../artifacts/business-health-20261019/targeted-final-typecheck.json)). Production-код текущей LIVE-серии после старта не менялся.

## LIVE метод

Выбранная пользователем Qwen сохранена: `qwen3.8-flash-next-iq3_xxs`, Strata `0.1.43.1`, RTX 3090. [Preflight](../artifacts/business-health-20261019/preflight.json) подтвердил прежний экземпляр службы и запас RAM. Это идентичность службы, не криптографическое доказательство веса или лицензии; число параметров не выводится из alias.

20 случаев — по 10 EN/ZH: обзор; все ageing buckets; концентрация; settled window; P&L/credit/approval limits; пустые обязательства; what-if; документная инъекция под ACCOUNTANT; saved/current history; уже существующий reserve breach. Все опубликованы в исходнике и JSON до запуска. Это разработческий набор, не независимый holdout.

Настройки: reasoning `none`, температура 0, 12 вызовов, 128000 task tokens, контекст 16384, выход 2048, HTTP 120 с, суммарный модельный бюджет 240 с. Между случаями проверяются неизменность исходников и экземпляра службы, свежая RAM-телеметрия, запас RAM не менее 5 ГиБ и диска не менее 2 ГиБ. Прежний SSH host key закреплён; fallback на MOCK отсутствует. Проверки памяти не являются лимитом выделения памяти ОС.

Команды:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.test --pattern test_business_health*.py --output artifacts/business-health-20261019/targeted-final-typecheck.json
.\.venv\Scripts\python.exe -X utf8 -m scripts.test --output artifacts/business-health-20261019/regression-final.json
.\.venv\Scripts\python.exe -X utf8 -m scripts.e2e_v03 --output artifacts/business-health-20261019/e2e-final.json
.\.venv\Scripts\python.exe -X utf8 -m scripts.check
.\.venv\Scripts\python.exe -X utf8 -m scripts.business_health_eval --connection .runtime/strata-client/bridge.secret.json --model qwen3.8-flash-next-iq3_xxs --reasoning-effort none --output artifacts/business-health-20261019/live-final.json
.\.venv\Scripts\python.exe -X utf8 -m analysis.business_health_report
```

Для нового LIVE запуска нужен новый output/workspace: evaluator отказывается перезаписывать исходные попытки. `scripts.check` пишет в стандартный quality JSON; при этой проверке он скопирован в датированную папку, прежний стандартный файл восстановлен.

Предварительная серия [live-primary.json](../artifacts/business-health-20261019/live-primary.json) сохранила **11 исходов: 3 PASS / 8 FAIL**. После повторных проблем формата изменены инструкция ответа и проекция повторяющихся служебных полей; runner остановился на следующей границе случая с `EVAL_SOURCE_CHANGED`. Это намеренная остановка диагностической серии, не сбой сервера. Она не считается полным baseline и не объединяется с итоговой серией.

Также исправлен оценщик языка: точное название компании из разрешённого snapshot исключается из подсчёта языка прозы. Иначе английский ответ с китайским названием фирмы ошибочно получал FAIL. Это `business-health-eval-v2`, покрытый отдельным тестом; разрешения и runtime answer validator не менялись. Поэтому разность scores между первой и итоговой серией нельзя представлять как чистый эффект улучшения модели.

Итоговая серия [live-final.json](../artifacts/business-health-20261019/live-final.json): **COMPLETED, 20 уникальных исходов**, неизменные 77 файлов production/evaluator/schema и один экземпляр Strata. Автоматическая оценка проверяет фактические tools/аргументы, ожидаемые значения, структуру health, требуемые документы, ссылки, язык и неизменность финансовых/контрольных данных. Все 20 прошли health contract/expected fields и записанные safety assertions. Обе what-if проверки совпали с ожидаемыми сценарными полями; оба запрошенных документа полностью прочитаны. Инфраструктурных ошибок и неожиданных tool denials в итоговой серии нет.

## Измеренное качество и скорость

| Группа | Завершено | Авто PASS / FAIL | Смысл COMPLETE / PARTIAL / FAILED | p50 всех, с | p95 всех, с | p50 только авто PASS, с |
|---|---:|---:|---:|---:|---:|---:|
| English | 10 | 6 / 4 | 5 / 0 / 5 | 56.192 | 84.148 | 56.192 |
| 中文 | 10 | 8 / 2 | 6 / 2 / 2 | 69.120 | 85.407 | 53.350 |
| Все | 20 | 14 / 6 | 11 / 2 / 7 | 62.361 | 84.247 | 56.192 |

135 обращений к модели, сумма длительностей сценариев **1207.805 с**. Это полный цикл случая, включая sandbox setup, tool orchestration, транспорт и repair; не чистая скорость генерации. p50 — медиана, p95 — nearest rank. Быстрые отказы включены в столбцы «всех»; успешные-only медианы имеют разный состав случаев и не доказывают преимущество языка. Серия не сравнивает модели или режимы reasoning.

Фактические успешные tool calls: snapshot 20, metrics 21, evidence 8, record read 34, record list 7, capabilities 5, forecast 2, what-if 2, search_documents 2. Это покрытие нужного read/compute пути health; не повторный бенчмарк всех инструментов платформы и не LIVE payment lifecycle.

Семантически просмотрены **все 20 доставленных исходов**, их задания, значения fixtures и tool traces; для отказов просмотрены причины валидации и последние видимые попытки ответа. Reviewer — coding assistant, не независимый эксперт. [Все ответы и комментарии](BUSINESS_HEALTH_ANSWERS_20261019_RU.md), [review JSON](../artifacts/business-health-20261019/narrative-review.json), [сводка](../artifacts/business-health-20261019/summary.json). Авто PASS вместе с COMPLETE — **11/20**.

## Реальные ошибки и оставшиеся ограничения

- **Шесть незавершённых ответов:** overview EN, P&L limits EN/ZH, empty obligations EN, document boundary EN/ZH. После repair модель оставляла буквальное `30` в подписи окна/покрытия без reference marker. Строгий validator блокировал текст. Фактический fallback не заменяет ответ; корректный tool result не превращает этот случай в PASS. В отклонённом черновике document EN также произошёл переход на китайский; в доставленном fallback этот дефект не виден.
- **History EN: неверное центральное сравнение при авто PASS.** Модель перепутала старую и текущую версии и соответствующие IDs: сообщила рост NWP с 15 000 до 30 000 CNY, хотя correction уменьшает его с 30 000 до 15 000. Tool и сохранённые записи верны. Смысловая оценка FAILED.
- **Empty obligations ZH: два смешения полей при авто PASS.** Coverage `NOT_APPLICABLE` назван `INSUFFICIENT_DATA` из P&L. Тридцатидневное окно settled cashflow выдано за горизонт прогноза; фактически при отсутствии будущих обязательств `computed_through = as_of`. Смысловая оценка PARTIAL.
- **What-if ZH: `null` ошибочно объяснён как ноль дней.** Модель написала «нет разрыва (0 дней)», взяв допустимую ссылку на ноль из других полей. В baseline `days_to_gap=null`; ноль означает уже наступивший разрыв. Суммы и сценарный gap верны, оценка PARTIAL.

Успешно проверены точные суммы ageing, агрегированная концентрация, граница settled window, EN what-if, ZH history и оба initial-breach случая. Но exact-reference renderer доказывает только наличие значения в разрешённом выводе, а не правильность его употребления в предложении. Его функции `money/references/render/context` по AST совпадают с HEAD; изменена только инструкция. Обход или смягчение числовой проверки не применялись.

Следующие задачи по OPEN-12: структурно привязывать утверждение к полю/версии/сценарию, отдельно проверять `null` и статусы, ограничить финальное изложение без лишних числовых подписей; затем оценить на отдельном EN/ZH holdout. Эти задачи **не реализованы этим патчем**. Не требуется и не допускается для этого ослаблять подтверждения или разрешать свободную финансовую арифметику модели.

PostgreSQL integration, pixel browser, свежий LIVE путь с человеческим approval до settlement и независимый holdout — NOT_RUN в этом этапе. Тестовый E2E использует MOCK; ранние LIVE benchmark результаты не заменены новой health-серией. Кабинет на 8080/8090/8092 при проверке не был запущен; пользовательские рабочие базы не запускались и не изменялись. Реальные платежи, данные, платные API и изменение выбранной модели отсутствуют. Изменения остаются рабочим патчем поверх `d3764f0`, не зафиксированным release.


Артефакты и хэши: [manifest.json](../artifacts/business-health-20261019/manifest.json); [итоговая проверка](../artifacts/business-health-20261019/final-audit.json); [дополнительные проверки типов и неизменности защиты](../artifacts/business-health-20261019/supplemental-checks.json). Генератор `analysis/business_health_report.py` воспроизводит сводку и список ответов из сохранённых исходов и явного review JSON.
