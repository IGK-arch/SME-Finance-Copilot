# Аудит готовности к подаче — SME Finance Copilot, Topic E

> **19 Oct Business health follow-up:** AUD-05 integration gap closed: shared typed metrics/forecast/what-if, saved results and agent card. Fresh regression 328 PASS / 4 PG SKIP, targeted17, E2E23/23 MOCK, static9/9. Qwen EN/ZH20 complete:14 strict PASS, but prose11 COMPLETE/2 PARTIAL/7 FAILED. OPEN-12 retains the narrative-quality blocker; overall HOLD and other findings remain. See [measured report](BUSINESS_HEALTH_AGENT_20261019_RU.md). The audit below is historical evidence, not a claim that health tools are still missing.

> **Последующее исправление, 19 октября:** AUD-01/K15 закрыт для synthetic sandbox на патче поверх указанного ниже HEAD. Целевые тесты 15/15; регрессия 311 PASS / 4 PG SKIP; HTTP E2E 23/23; golden 5/5; static 9/9. [Отчёт и ограничения](SETTLEMENT_FIX_20261019_RU.md). Ниже сохранён первоначальный аудит и его результаты до исправления; другие замечания не закрыты этим патчем.

19 октября 2026, Москва. Проверяемый код: `d3764f0a5155fe0153e3b7d807f0fa37d78640d3`, ветка `security-hardening`. Начальный рабочий каталог был чистым. Время первичных проверок записано в UTC; 18 октября вечером UTC соответствует 19 октября в Москве.

**Вердикт: сильный работающий синтетический прототип, но текущую комплектацию нельзя считать готовой к окончательной отправке.** Основной финансовый путь воспроизводится. Обнаружен новый дефект признания settlement; пакет содержит расходящиеся утверждения; презентация оставляет незаполненные поля и одну заметную ошибку вёрстки. Успешная регрессия не закрывает эти проблемы.

Это инженерный аудит coding assistant, не независимая сертификация безопасности, не юридическое заключение и не прогноз места в конкурсе. Баллы жюри и «вероятность победы» не выдумываются.

## 1. Метод и границы

Прочитаны CLAUDE/AGENTS, навигация пакета, применимые разделы MASTER_SPEC и решения, R1, статусы исследовательских R2/R3, I01–I36, T001–T100, V03, английский комплект подачи, текущие отчёты. Проверены критические пути денег, подтверждений, worker, сверки, инструментов/результатов агента, новой бизнес-аналитики, HTTP, парсинга и on-chain. Проведены свежая регрессия, E2E, golden, static/dependency/security checks и отдельные проверки с намеренно ошибочным наблюдением банка.

Все 17 страниц предоставленного `SME Finance Copilot — Final Pitch.pdf` извлечены и визуально просмотрены после рендера Poppler. SHA-256 и текст сохранены в [pitch-extracted.json](../artifacts/submission-audit-20261019/pitch-extracted.json); исходный PDF не изменён. Это проверка PDF, не проверка устного выступления на время.

Браузер: установленный Edge 155.0.4283.45, отдельная временная синтетическая база, шесть разделов × три ширины. Действующие базы пользователя, `.runtime/pg-workspace`, выбор модели и финансовые ограничения не менялись. Новые LIVE-вызовы, реальные платежи, отправка on-chain транзакций, загрузка моделей, публикация и merge не выполнялись.

Глубокая ручная проверка сосредоточена на критических границах; это не утверждение о построчной проверке всех 621 отслеживаемого файла и всех исторических ответов моделей. Исторические результаты модели использованы с их исходными ограничениями. Зафиксировано 157 хешей исходников/контрактов/проверок/документов в [source-snapshot.json](../artifacts/submission-audit-20261019/source-snapshot.json).

## 2. Что реально выполнено

| Проверка | Результат | Доказательство / ограничение |
|---|---|---|
| `python -X utf8 -m scripts.test --output artifacts/submission-audit-20261019/regression.json` | 300 запущено: **296 PASS, 4 SKIP, 0 FAIL** | [Регрессия](../artifacts/submission-audit-20261019/regression.json); четыре PostgreSQL integration tests не настроены |
| T001–T100 в этой регрессии | **95 PASSED, 5 NOT_RUN** | T023, T031, T032: нет обучения/holdout; T094: прежнее browser evidence не соответствует текущим файлам; T097: нет OS-изоляции private truth |
| V03, 25 пунктов | 9 PASSED; 3 PARTIAL; 5 NOT_RUN; 6 DEFERRED_MODEL; 2 EVIDENCE_RECORDED | Реестр отстал от части реализованных функций; автоматически превращать deferred в PASS нельзя |
| `python -X utf8 -m scripts.e2e_v03 --output artifacts/submission-audit-20261019/e2e.json` | **23/23 PASS** | HTTP, cookie, точное подтверждение и step-up, worker, отдельный simulator, потеря ответа, остановка/перезапуск сервера, reconciliation. MOCK, без решения LIVE-модели |
| `python -X utf8 -m scripts.demo --lost-response --output artifacts/submission-audit-20261019/golden` | **5/5 SETTLED; COMPLETED; Δ=0** | [Golden](../artifacts/submission-audit-20261019/golden/golden-latest.json), независимый evaluator: cash 29 000 CNY, minimum 20 000, debt/payables 0, missed deadlines 0, 6 движений |
| compileall, ruff lint/format, mypy, `node --check` для пяти web JS, `pip check` | **10/10 PASS** | [Команды и вывод](../artifacts/submission-audit-20261019/static-checks.json). Это отдельные команды, не повторный запуск `scripts.check` |
| Пины установленных пакетов | Несоответствий не найдено | [Inventory](../artifacts/submission-audit-20261019/installed-dependencies.json); не независимая проверка лицензий |
| `python -m scripts.security_scan --history --output .../security-scan.json` | Текущие tracked файлы PASS; OSV 80 пакетов PASS; history **FAIL** | 15 находок `public_ipv4` в старых коммитах — принятый пользователем K13. Exit 1 сохранён; история не переписывалась. Это ограниченный scanner, не доказательство отсутствия любых секретов |
| `python -m analysis.submission_browser_runner` | **18/18 экранов**, 7 smoke assertions PASS | [Browser JSON](../artifacts/submission-audit-20261019/browser-smoke.json), 390/768/1440 px, китайское название, MOCK label, reload session, отсутствие token storage. Не полный E2E через браузер и не WCAG/usability study |
| `python -m analysis.submission_audit_probes` | Два дефекта settlement воспроизведены; проверены tenant tag и contract tools | [Первичные наблюдения](../artifacts/submission-audit-20261019/adversarial-probes.json); обнаружение дефекта не считается успешной приёмкой |
| Публичный Sepolia RPC, только чтение | receipt `0x1`, block 11941459, value 0, 65 bytes, 72 records, hash совпал с записью | [Проверка](../artifacts/submission-audit-20261019/onchain-public-check.json). Локальную историческую БД этой командой повторно не верифицировали |
| GitHub | CI SUCCESS на `d3764f0`; PR #4 OPEN; repo PRIVATE; default main | [Состояние](../artifacts/submission-audit-20261019/github-readiness.json). Локальная main — `3ef8441` |

Новые диагностические файлы прошли отдельные syntax/lint/type/format checks после добавления; результат сохраняется в `audit-tooling-checks.json`. Полная регрессия выше относится к неизменённому прикладному коду, до добавления диагностик и документов.

Свежий LIVE прогон на выбранной Qwen **NOT_RUN**: проверка локальных портов 8080/8092/18443 дала timeout. Это не доказывает, что удалённый сервер выключен. Мост и сервер в рамках аудита не перезапускались. PostgreSQL/RLS на актуальном HEAD, чистая установка на другом компьютере, новое holdout-исследование и пользовательская проверка удобства также NOT_RUN.

## 3. Оценка по критериям

| Критерий | Что подтверждено | Что мешает максимальному результату |
|---|---|---|
| Выполнение задач — 40% | Все три направления Topic E присутствуют; планирование/валидация/approval/worker/банк/reconciliation работают в независимой песочнице; есть честные INFEASIBLE и UNKNOWN | Ошибка settlement ниже; новый Business health не полностью доступен как compute tool; отсутствует свежий единый LIVE путь от свободной EN/ZH просьбы до финального результата на HEAD |
| Безопасность и соответствие — 30% | Ролевые границы, точный payload hash, step-up, актуальные preconditions, reserves, стабильный key, status-before-resend, kill switch, запрет dangerous tools, audit, input/HTTP hardening реально проверяются | Сверка смотрит недостаточно полей; PostgreSQL/RLS свежим прогоном не проверен; OS isolation, vault, TLS/SSO — известные границы; нельзя обещать «все числа/все исходы доказаны» |
| Инновационность и взаимодействие — 30% | Убедительный сценарий одного владельца, сравнение вариантов, объяснение разрыва, восстановление UNKNOWN, связь источника с действием и результатом; настоящие экраны в презентации | Нет исследования с владельцами МСП, измеренной экономии времени, независимого holdout; «никто больше так не делает» не доказано; LIVE-демо агента пока заменено MOCK |
| On-chain, дополнительно 0–5 | Публичная существующая транзакция подтверждена; тест действительно обнаруживает переписанный закреплённый префикс | Бонус не гарантирован. Это proof of audit integrity, не доказательство достоверности исходных фактов или исполнения платежа. Нужен доверенный сохранённый tx hash и локальные записи |

Рабочая система сильнее обычного чата с рекомендациями: здесь есть отдельная машина состояний исполнения и независимый oracle. Именно это стоит защищать демонстрацией, а не перечнем библиотек. Новизна комбинации для данного сценария обоснована архитектурой; глобальное первенство рынка не установлено.

## 4. Подтверждённые находки и приоритеты

### AUD-01 — P0: ложное SETTLED при неверном получателе/назначении

Статус после отдельного исправления: **FIXED, synthetic adapter only**; см. дополнение выше. Следующий текст описывает исходное воспроизведение.

`finance/execution.py:refresh`: действие ищется по `provider_ref OR stable_key`. Перед SETTLED проверяется сумма, но не эквивалентность наблюдаемого получателя/назначения утверждённой команде. Allocation отдельно проверяет counterparty/reference, поэтому действие и обязательство расходятся.

В двух новых временных компаниях: обычный одобренный DRAW_LOAN, затем точное одобрение payroll 80 000 CNY, исполнение в sandbox. В полученном observation изменялось ровно одно поле: `counterparty` либо `reference`; сумма, provider ref, key и cash balance сохранялись. Получено:

- `action_status=SETTLED`, `reservation_status=RELEASED`;
- payroll outstanding = **8 000 000 minor / 80 000 CNY**;
- `stopped=0`, reconciliation `matched=true`, discrepancy 0.

Это проверка ошибочного/несогласованного ответа доверенного провайдера, а не доказательство удалённого взлома. Однако итоговая надпись «settled and reconciled» недостаточна для доказательства оплаты именно требуемого обязательства.

Исправление: идентичность provider operation и согласованность key/ref должны быть однозначны; проверять договорённые поля currency/kind/payee/obligation и сумму до завершения действия. Несоответствие оставляет наблюдённые деньги в ledger, но переводит исполнение в явное расследование/остановку и не освобождает резерв как успешный. В контракте sandbox сейчас CNY фиксирована; для внешнего адаптера валюту нужно передавать и проверять явно. Нельзя «исправить» дефект удалением реального движения или подменой получателя утверждённым.

Условия закрытия: тесты wrong counterparty/reference, конфликт key/ref, amount mismatch, повторное наблюдение, incoming draw и outgoing payment; отсутствие ложного COMPLETE у plan/case; полный regression + E2E + golden после исправления. В этом аудите прикладной код не исправлялся, находка **OPEN**.

### AUD-02 — P0: сборка подачи и доступ жюри не зафиксированы

Репозиторий PRIVATE, PR [#4](https://github.com/IGK-arch/SME-Finance-Copilot/pull/4) OPEN. Зелёный [CI](https://github.com/IGK-arch/SME-Finance-Copilot/actions/runs/39164169351) подтверждает ветку, не default main. Судья с одной ссылкой из PDF может не получить ни доступ, ни последние исправления.

Нужны выбранный submission commit/tag или архив с manifest, разрешённый правилами доступ жюри и проверка открытия с чистой учётной записью. Автоматически публиковать private repo или сливать PR нельзя: это отдельное решение владельца. Текущие новые audit files ещё не входят в `git ls-files`, поэтому текущий экспортёр их пропустит до включения в состав пакета.

### AUD-03 — P0: финальная презентация и комплект не завершены

PDF существует, но страницы 1/16/17 содержат `[Team name]`, имена/университеты/контакты/фото/роли-заглушки. На странице 12 `92/100` переносится как `92/10` и отдельный `0`. В PDF только одна настоящая URI-аннотация — Sepolia; кнопка Live demo не ведёт на демо, GitHub напечатан текстом.

Видео `.mp4/.webm/.mov` и редактируемая `.pptx/.odp` в репозитории не найдены, в том числе при поиске ignored files вне dependency caches. Скрипт сам говорит, что видео ещё не записано. По R1 общий список называет видео optional, а evidence clause упоминает sandbox logs + demo video: безопаснее подготовить короткое видео или получить подтверждение организатора, а не писать «Submitted separately» без файла. Командная eligibility не устанавливается по коду: проверить 2–5 участников, студенческий статус, требования международного трека и очное участие по применимому brief.

[Правки всех 17 слайдов](submission/PITCH_REVIEW_20261019.md) содержат готовые точные формулировки. PDF не редактировался, данные участников не выдумывались.

### AUD-04 — P0 для доказательности: противоречивые метрики и утверждения

В deck 274 PASS / 4 SKIP и 96/100, в technical documentation 278 run / 7 SKIP и 21/21 E2E; свежая база — 296/4, 95/100, 23/23. 95 вместо старых 96 связано с отсутствием валидного текущего browser evidence для T094, а не с доказанной поломкой китайского текста. Новые browser screenshots положительны, но acceptance collector ещё не интегрирован с этим harness.

В demo-script написано «real-model quality NOT_RUN», хотя исторические LIVE серии выполнены. Корректно: **демо MOCK; историческая Qwen оценена; свежий LIVE E2E на данном commit NOT_RUN**. Реестры V03/OPEN и synthetic data card также отстали. Требуется единый dated evidence index; старые raw results нельзя переписывать новыми цифрами.

Заявления «A copilot that cannot change a number», «Every outcome proven», «Nothing ... has to change ... real bank», «No second payment is possible» шире доказательства. Безопасный язык: числовые карточки строятся кодом; текст модели может ошибаться; отсутствие дубля проверено в перечисленных сбоях при контракте stable idempotency.

### AUD-05 — P1: Business health не подключён к вычислительным инструментам агента

`compute.analysis` → проекция Money в `cases.py` даёт ageing, concentration, coverage, net working position, days to gap. `ToolRegistry.calculate_business_metrics` вызывает прежний `compute.metrics`: только confirmed cash, receivables, payables due, reserve и P&L insufficient data. Registry не содержит отдельного health tool. Проверено [probe](../artifacts/submission-audit-20261019/adversarial-probes.json).

Доступ к исходным records есть, но это не эквивалент готового проверяемого расчёта: нельзя заставлять LLM вручную пересчитывать проценты. Подключить typed calculation с snapshot/version/evidence, expose capability, добавить EN/ZH запросы на долю крупнейшего клиента, возраст долга, cash coverage и отсутствие знаменателя. Затем проверить карточки и narrative на одной и той же базе.

### AUD-06 — P1: свежие LIVE и PostgreSQL release gates отсутствуют

Предыдущие Qwen none/medium: строгие **87/100 и 92/100**; полностью COMPLETE по ручному просмотру **77 и 80**; одновременно strict PASS + COMPLETE **76 и 75**. Поэтому 92% нельзя называть «92% полностью правильных финансовых ответов». p50/p95 полного сценария: none 30,946/71,902 с, medium 28,236/53,618 с. Один исход на режим/сценарий; разработческий набор; 67 EN и 33 ZH разных задач, не paired translations; ручной просмотр coding assistant, не независимый эксперт. Источник: [reasoning report](REASONING_100_RESULTS_RU.md).

Новая серия на выбранной Qwen нужна после исправления AUD-01/05: несколько свободных задач с продолжением до точного owner approval и финальной сверки; негативные ветки unsafe request, incomplete registry, doc injection, stale facts, insufficient data. Не заменять ими исходные FAIL и не менять бюджеты скрыто. Следом отдельная чистая PostgreSQL test DB и RLS tests, не база пользователя. Не запускать заново 500 альтернатив ради количества; выбранная Qwen остаётся прежней.

### AUD-07 — P1: on-chain защищает ограниченный префикс, а не всю истину

65 bytes подтверждены: 9-byte magic + 16-byte tenant tag + 8-byte count + 32-byte chain head. Tenant tag — SHA-256 от публичного постоянного prefix и tenant ID, усечённый до 16 bytes. Секретной/случайной соли нет; известный `demo_company` легко проверяется словарём. Поэтому «only hashes / no identifier» требует исправления: публикуются pseudonymous tag и счётчик, а transaction metadata публичны. Финансовые суммы и тексты записей payload не содержит.

K01 остаётся частично mitigated: проверяется закреплённый префикс относительно сохранённого tx hash; новые записи после anchor не защищены этим anchor. Любому проверяющему для повторного вычисления нужны сами локальные записи; публичный explorer не доказывает их смысл. `verify` проверяет mined block, но не receipt status/finality depth; свежая внешняя проверка receipt была выполнена отдельно. Следует задать политику finality, закрепления trusted tx hash и доступа к синтетическому evidence, не публиковать реальные business logs.

### AUD-08 — P1: права и экспорт требуют отдельного финального прохода

У проекта есть MIT LICENSE. Старый data card утверждает, что лицензии и third-party dependencies нет; это неверно для текущего кода. Runtime ID Qwen не подтверждает точное число параметров, оригинальный weight manifest и лицензию. Запись dependency inventory `NOT_APPLICABLE_NO_WEIGHTS_DOWNLOADED` относится к раннему локальному срезу, не к сегодняшнему self-hosted использованию. Нужны отдельные происхождение и лицензия фактических весов/движка; «125B» не превращаем в технически подтверждённую характеристику.

Права на публичное распространение пользовательских R1–R3 отмечены UNKNOWN в самом data card. `submission_copy` копирует все tracked files, включая эти документы. Dry review выявил 4 изменяемых файла (3 исторических artifact и test_security_hardening) из-за общего regex scrub; это не чистая побайтовая копия. Экспорт отдельно не запускался и его работоспособность не доказана. Нужны curated manifest, согласование прав, сохранение оригинальных measurements и явный журнал редактирования производной публичной копии; затем проверки именно экспортированного дерева.

### AUD-09 — P1: CI не включает главный HTTP E2E и браузер

В workflow есть security scan, static, tests, golden, benchmark, report, но нет `scripts.e2e_v03`, браузерного теста и PostgreSQL job. Local PASS не заменяет reproducible release gates. Security scanner может вернуть NOT_RUN при недоступном OSV без failure; для release нужен явный статус «проверено» или принятая exception, а не общий зелёный badge. Actions закреплены по SHA и token read-only — это уже реализовано хорошо.

### AUD-10 — P2: убедительность и удобство без неподтверждённого маркетинга

Сделать 2–5 коротких наблюдаемых заданий с владельцами/бухгалтерами: понять gap, отличить expected от settled, выбрать вариант, объяснить approval, восстановить UNKNOWN. Измерять completion/time/error, не обещать экономию до измерения. Отдельно keyboard/focus/contrast/screen reader и внутренний horizontal scroll таблиц на телефоне; отсутствие overflow всей страницы недостаточно. Нужен независимый документный holdout: новые EN/ZH компании, похожие IDs, даты, конфликтующие версии, отрицание, таблицы, частичные суммы, отсутствие источника. Лексический retrieval и text-only PDF без OCR обозначать прямо.

## 5. Что оставить и как показать

Сохранить один сильный сюжет: cash 120 000 → три выплаты → gap 70 000 и hard reserve 20 000 → нужно 90 000 net → gross 91 000 → exact approval → lost response → lookup same key → 5 settled → 29 000 и Δ0. На математике и independent evidence этот сюжет выдержал повторный запуск.

Короткая заявка на отличие: «We link each cash-gap decision to its source facts, exact approval and independently observed settlement, including recovery when the bank response is lost.» Не утверждать, что другие продукты вообще не исполняют платежи: R3 — исследовательские заметки с собственными оговорками, не доказательство всеобщего отсутствия конкурентов.

Рекомендованный порядок 10-минутного выступления: проблема/польза 1 мин; 3 функции Topic E 40 с; живой путь/видео 3 мин; архитектура и безопасность 1,5 мин; EN/ZH Copilot и честный fail 1 мин; измерения/границы 1 мин; anchor 30 с; команда/заключение 20 с. Это план длительности, не результат репетиции. 17 слайдов не запрещены сами по себе; несколько технических страниц лучше вынести в appendix.

## 6. План закрытия перед отправкой

| Приоритет | Работа | Критерий готовности |
|---|---|---|
| P0 | AUD-01: semantic settlement identity | Новые негативные тесты отказывают безопасно; деньги не исчезают; regression/E2E/golden зелёные |
| P0 | AUD-02/03: release commit, доступ, команда, PDF и evidence video | Проверено с чистого окружения/учётной записи; в PDF нет placeholders и разрыва 92/100; ≤10 мин выступление, видео ≤5 мин |
| P0 | AUD-04: единый набор датированных утверждений | Deck/docs/manifest совпадают с одной проверенной сборкой; исторические raw результаты сохранены |
| P1 | AUD-05/06: health tool + selected Qwen complete path + PG | Точная одинаковая аналитика в UI/tool; несколько EN/ZH lifecycle smoke; четыре PostgreSQL tests реально выполнены |
| P1 | AUD-07/08: anchor wording, лицензии и export | Проверяемый ограниченный claim, trusted anchor ref, подтверждённый состав и права на распространяемые файлы |
| P1 | AUD-09: CI release gates | E2E/браузер/PG и обязательный статус supply-chain check проверяют submission tree |
| P2 | AUD-10: независимый holdout и usability | Сырые наблюдения, фактические показатели, ошибки и границы опубликованы без cherry-picking |

Проверить актуальный международный brief: [официальный сайт](https://fintechathon.g-ican.com/) на момент проверки содержит international deadline **20 OCT**, timezone UTC+8. Его общая AI-таблица на главной странице называет Completeness/Innovation/Business Value, тогда как приложенный R1 и пользовательский скриншот — Task completion/Security/Innovation & interaction. Здесь применена именно предоставленная пользователем рубрика 40/30/30; homepage не принят за молчаливую замену правил international track. Детальное время 23:59 UTC+8 взято из R1, не заново подтверждено на главной: это 15:59 UTC / 18:59 Москвы, а не округлённые 16:00 UTC. [Сохранённые выдержки проверки](../artifacts/submission-audit-20261019/official-rules-check.json).

## 7. I01–I36 и честная traceability

Все 36 сопоставлены с текущими исходами существующих тестов и новыми fault probes в [invariant-review.json](../artifacts/submission-audit-20261019/invariant-review.json). 29 — COVERED_SYNTHETIC, 5 — PARTIAL, 2 — PARTIAL_CONFIRMED_FINDING. COVERED_SYNTHETIC означает ограниченный проверенный сценарий, не доказанность всех возможных состояний.

- I05/I27: exact approval работает, но settlement identity ломает сквозное утверждение о результате.
- I20: cutoff проверяется; обучения и temporal validation нет.
- I24/I28: процесс/права приложения проверяются; OS isolation отсутствует, свежий PG/RLS пропущен.
- I34: raw measurements честные, но package claims требуют синхронизации.
- I35: MIT кода не доказывает права на исходные документы, данные или фактические веса.

Остальные I и связанные T перечислены с исходной формулировкой и code mapping в JSON. Историческая [матрица](ACCEPTANCE_MATRIX.md) не переписана как будто она получена новым запуском. Отдельная browser smoke не повышает автоматически T094 или весь V03 до PASS.

## 8. Изменения этого аудита

Добавлены этот подробный отчёт, английский readiness review и slide review, три воспроизводимых diagnostic/browser harness файла в `analysis/`, первичные результаты в `artifacts/submission-audit-20261019/`. В CLAUDE, CURRENT_STATE_RU, TECHNICAL_REPORT_RU и index подачи добавлен актуальный указатель; устаревшие утверждения submission docs, data card и OPEN_REGISTER приведены к наблюдаемому состоянию. Код денег/полномочий/модели и исходный PDF не менялись. Новые ошибки не замаскированы исправлением критериев или удалением неуспешных исходов.
