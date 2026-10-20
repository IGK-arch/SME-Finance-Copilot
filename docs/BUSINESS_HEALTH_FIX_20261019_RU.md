# Business health: исправление завершённости и смысла ответов

**19 октября 2026, Москва. Статус: исправление реализовано; итоговый LIVE прогон завершён — 20/20 PASS, все 20 ответов просмотрены по смыслу.** Продолжение [первой интеграции](BUSINESS_HEALTH_AGENT_20261019_RU.md). Прежние 20 исходов и их оценки сохранены без изменений.

## Измеренный результат

| Показатель | Прежние 20 | После исправления |
|---|---:|---:|
| Строгий автоматический исход | 14 PASS / 6 FAIL | 20 PASS / 0 FAIL |
| Английский, автоматический | 6/10 PASS | 10/10 PASS |
| Китайский, автоматический | 8/10 PASS | 10/10 PASS |
| Просмотр доставленных ответов | 11 COMPLETE / 2 PARTIAL / 7 FAILED | 20 COMPLETE |
| p50 полного сценария | 62.361 с | 24.135 с |
| p95 полного сценария | 84.247 с | 51.928 с |
| Сумма длительностей случаев | 1207.805 с | 578.457 с |
| Записанные обращения к модели | 135 | 74 |

Новая серия не содержит tool errors, незавершённых workflow или зарегистрированных инфраструктурных ошибок. Все записанные safety assertions прошли. p50 EN — 24.370 с, ZH — 23.463 с. Среди **11 пар**, которые и до, и после были автоматическими PASS и смысловыми COMPLETE, медиана отношения времени «после / до» — **0.604** (около 40% меньше). Общие p50/p95 включают прежние неуспехи и repairs, поэтому не заменяют это парное сравнение. Время включает fixture/setup, tools, транспорт и финализацию; это не tokens/s и не изолированный inference benchmark. Одна серия на вариант, статистическая устойчивость не установлена.

Qwen и служба модели совпали с baseline; cases, параметры, бюджет и grader проверены программно. Изменилось представление ответа и момент завершения tool phase. Поэтому улучшение относится к системе с серверным формированием health-текста, а не к свободной прозе модели.

[Сводка и сравнение каждого случая](../artifacts/business-health-fix-20261019/summary.json), [все запросы и доставленные ответы](BUSINESS_HEALTH_FIX_ANSWERS_20261019_RU.md), [смысловые заметки](../artifacts/business-health-fix-20261019/narrative-review.json).

## Проверка прежних ошибок

| Проблема baseline | Что подтверждено в новом LIVE |
|---|---|
| Шесть отклонённых финальных текстов: overview EN, P&L EN/ZH, empty obligations EN, documents EN/ZH | Все шесть завершены с REFERENCES_VALIDATED; запрет несвязанных чисел не ослаблен |
| Saved history EN: перепутаны result IDs и 30000/15000 | Сохранённый расчёт показывает 30000 CNY, текущий — 15000 CNY, каждый с собственным правильным snapshot/result; выдуманного роста нет |
| Empty obligations ZH: coverage спутан с P&L и горизонтом | Coverage неприменим из-за отсутствия payables; P&L имеет отдельный статус; computed-through равен as-of, а не окну settled cashflow |
| What-if ZH: null gap превращён в ноль | Baseline прямо указывает отсутствие разрыва в вычисленном горизонте; scenario — 7 дней; ноль отдельно проверен в initial-breach EN/ZH |

Смысловой просмотр охватил **20/20 полных доставленных ответов**, selections и относящиеся к ним tool evidence: суммы, labels, текущие/сохранённые IDs, null/zero, статусы, forecast scope, полномочия и документные источники. Проверял coding assistant, не независимый финансовый эксперт; автоматический PASS не использовался как замена просмотра текста. Документные случаи включают полный read недоверенного HEALTH-NOTE, явное расхождение cash и отказ признавать текст источником approval. Успешное чтение документов не доказывает универсальный semantic RAG.

## Что исправлено

В прежней серии шесть текстов блокировались за необвязанный ссылкой литерал `30`, а три автоматических PASS содержали ошибки смысла. Новая версия не разрешает сырые числа и не повышает лимит repairs. Для ограниченного health-отчёта модель выбирает разделы и реальные IDs в структурированном JSON; сервер формирует подписи и значения вместе, затем проверяет маркеры прежним `answers.render`.

| Файл | Изменение |
|---|---|
| `finance/health_answers.py` | Контракт `health-answer-v1`, определение требуемых health-разделов, каталог разрешённых текущих/сохранённых/сценарных результатов, проверка выбора, связанное с полями двуязычное представление |
| `finance/answers.py` | Дополнительный presentation-контракт контекста; прежний общий путь и exact-reference renderer сохранены |
| `finance/workflows.py` | Health-валидация в существующем bounded repair; закрытие tools после необходимых чтений; честная маркировка серверного health-текста |
| `tests/test_health_answers.py` | 16 новых тестов: прошлые traces, ошибки смысла, недопустимые ID/поля, страницы, документы, смешанные запросы и полный workflow |
| `analysis/health_answer_fix_report.py` | Воспроизводимое сравнение с сохранённым baseline, проверка неизменности cases/бюджетов/grader, все ответы и отдельная смысловая оценка |
| `contracts/RUNTIME.md`, ADR 0008 | Версионированный контракт и границы применения |

Текущий результат определяется по последнему snapshot, реально прочитанному в этом workflow. Подставить на его место даже существующий ID старого расчёта нельзя. Исторический расчёт попадает в каталог только после полного чтения и проверки хэша страниц; порядок выдачи списка не определяет хронологию. Ответ показывает каждое наблюдение отдельно, не складывает версии и не выводит недоказанный рост/снижение.

`days_to_gap=null` теперь формирует фразу «нет разрыва в вычисленном горизонте», а ноль — «уже ниже резерва». Coverage с пустым знаменателем имеет собственную подпись; P&L `INSUFFICIENT_DATA` показывается только как P&L. Горизонт берётся из `forecast_scope.computed_through`, а не из settled window. Все текущие и сценарные значения сохраняют результат, поле и snapshot.

Документы остаются недоверенным текстом. Для сравнения с cash извлекается только явно подписанная сумма confirmed cash / 已确认现金 в CNY/RMB с двумя десятичными знаками. Сравнение целочисленное, без валютной конвертации; иные формы имеют явный статус отсутствия сопоставимого литерала. Совпадение чисел не подтверждает достоверность документа; расхождение не меняет финансовые факты. Ни документ, ни ACCOUNTANT не получают права approval.

## Защита и границы

Нет нового инструмента исполнения, обхода required reads, автоматического вызова tools от имени модели или успешного fallback после неверного JSON. Модель действительно выбирает tools и итоговый отчёт. Если она нарушает контракт после предусмотренного repair, результат остаётся PARTIAL. Финансовая арифметика и числа не генерируются моделью.

Выполнение, OWNER approval, payload hash, preconditions, reserves, tenant isolation и независимая сверка не менялись. Пользовательские рабочие базы не трогались. Только синтетические fixtures и ранее выбранная Qwen на Strata; платные API, реальные платежи и новые модели не использовались.

Это улучшение составной системы **«LLM выбирает данные/разделы → сервер формирует точный health-ответ»**. Оно не доказывает улучшение самостоятельной финансовой прозы Qwen. Контракт ограничен основными агрегатами health и выбранными сравнительными разделами. Смешанные действия и ряд более широких задач сохраняют общий workflow. Языковая маршрутизация EN/ZH эвристическая; другие языки здесь не проверены. Отдельные invoice-разборы, произвольные советы, переводы и общий document QA не покрываются этим рендерером. Документное сравнение не является общим семантическим анализом текста.

## Проверки и метод повторения

Целевые **16/16 PASS**: [артефакт](../artifacts/business-health-fix-20261019/targeted-final.json). Проверка на старых tool traces — офлайн-регрессия, не новый вызов модели. Отдельный scripted LIVE-протокол использует `OFFLINE_TEST_FIXTURE` и проверяет интеграцию workflow, не качество Qwen. Первоначальный тест статуса coverage ошибочно запрещал P&L-статус во всём ответе; assertion уточнён до строки coverage, обе семантики проверяются отдельно.

Предварительная новая LIVE проба сохранила **6 исходов: 5 PASS / 1 FAIL** в [live-health-fixed.json](../artifacts/business-health-fix-20261019/live-health-fixed.json). Обзор EN сделал лишний запрос страницы за концом записи; ответ был корректен, но строгий FAIL сохранён. После добавления завершения при достаточном evidence и явного документного сравнения runner остановился на границе случая по хэшу кода. Это диагностика, не часть итоговых двадцати и не замена прошлых неуспехов.

Итоговая серия: [live-health-final.json](../artifacts/business-health-fix-20261019/live-health-final.json). Те же 20 EN/ZH cases, fixture-параметры, evaluator `business-health-eval-v2`, Qwen `qwen3.8-flash-next-iq3_xxs`, reasoning `none`, temperature 0, 12 calls / 128000 task tokens / context 16384 / output 2048, timeout 120 с / модельный бюджет 240 с. Ресурсные пороги, SSH pin, отсутствие fallback и проверки источников сохранены. Идентичность службы не доказывает SHA весов или лицензию.

```powershell
.\.venv\Scripts\python.exe -X utf8 -m scripts.test --pattern test_health_answers.py --output artifacts/business-health-fix-20261019/targeted-final.json
.\.venv\Scripts\python.exe -X utf8 -m scripts.test --output artifacts/business-health-fix-20261019/regression-final.json
.\.venv\Scripts\python.exe -X utf8 -m scripts.e2e_v03 --output artifacts/business-health-fix-20261019/e2e-final.json
.\.venv\Scripts\python.exe -X utf8 -m scripts.check
.\.venv\Scripts\python.exe -X utf8 -m scripts.business_health_eval --connection .runtime/strata-client/bridge.secret.json --model qwen3.8-flash-next-iq3_xxs --reasoning-effort none --output artifacts/business-health-fix-20261019/live-health-final.json
.\.venv\Scripts\python.exe -X utf8 -m analysis.health_answer_fix_report
```

Фактически завершены:

| Проверка | Результат | Артефакт |
|---|---|---|
| Новые целевые тесты | 16 PASS | [targeted-final.json](../artifacts/business-health-fix-20261019/targeted-final.json) |
| Полная регрессия | 348 тестов: 344 PASS / 4 PostgreSQL SKIP / 0 FAIL | [regression-final.json](../artifacts/business-health-fix-20261019/regression-final.json) |
| HTTP E2E | 23/23 PASS, MOCK | [e2e-final.json](../artifacts/business-health-fix-20261019/e2e-final.json) |
| Статика, типы, формат | 9/9 PASS | [quality-final.json](../artifacts/business-health-fix-20261019/quality-final.json) |
| T001–T100 | 95 PASS / 5 NOT_RUN | В полном regression artifact |
| V03 | 9 PASS / 3 PARTIAL / 5 NOT_RUN / 6 DEFERRED_MODEL / 2 EVIDENCE_RECORDED | В полном regression artifact |
| Новый LIVE20 на Qwen | 20 PASS, 20 смысловых COMPLETE | [live-health-final.json](../artifacts/business-health-fix-20261019/live-health-final.json) |

Дополнительно mypy/ruff/format проверили новые тесты и генератор отчёта; `git -c core.whitespace=cr-at-eol diff --check` прошёл. При расширении typecheck на новый тестовый файл выявлены 8 замечаний аннотаций/Optional narrowing: [первый исход](../artifacts/business-health-fix-20261019/supplemental-checks-first.json). Добавлены типы fixture/patch и явные non-null assertions; production-код не менялся. [Повтор typecheck/lint/format](../artifacts/business-health-fix-20261019/supplemental-checks.json) прошёл для всех пяти файлов; [повтор 16 тестов](../artifacts/business-health-fix-20261019/targeted-type-final.json) — 16 PASS. Полная регрессия выше выполнена до этой правки аннотаций теста, на том же production-коде. Хэши 78 замороженных LIVE source files проверены после прогона. Сверены неизменные execution/worker/validator/payload-check и AST прежних `answers.money`, `references`, `render`. [Финальная сверка](../artifacts/business-health-fix-20261019/final-audit.json), [манифест кода и артефактов](../artifacts/business-health-fix-20261019/manifest.json).

Для нового LIVE повтора нужен новый output/workspace; перезапись предыдущих попыток запрещена evaluator. Standard quality JSON после проверок восстановлен, результаты этапа сохранены в датированной папке. Код — незакоммиченный патч поверх `d3764f0a5155fe0153e3b7d807f0fa37d78640d3`, с сохранением предыдущих пользовательских изменений.

## Оставшиеся ограничения

Девять конкретных дефектных исходов закрыты в поддержанном health-пути. **OPEN-12 остаётся для расширенной проверки**: это те же development cases, отдельный EN/ZH holdout и устойчивость перефразировок не измерены; выбор intent, источника и параметров сценария всё ещё зависит от модели/маршрутизации. Типизированный текст не является решением произвольных финансовых вопросов. Нового полного LIVE100/500, PostgreSQL, pixel UI и LIVE платёжного lifecycle в этой итерации не было. Работающий кабинет не перезапускался этим тестом; LIVE исполнялся в отдельных synthetic workspaces. Общая готовность подачи остаётся HOLD по прежним release/access/PDF вопросам; результаты не означают отсутствие всех дефектов платформы.
