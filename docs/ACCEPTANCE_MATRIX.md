# Acceptance matrix — original I01–I36, T001–T100, W01–W36

Generated 2026-10-13T00:24:00.124902+00:00 from actual artifacts/regression-agent-data-v3.json and hash-checked browser-smoke.json.
VERIFIED means demonstrated within the stated synthetic local scope. It is not full production acceptance.
PARTIAL means a requirement has remaining work; MISSING/IMPLEMENTED_UNVERIFIED/BLOCKED are never counted as verified.
Source checklist text remains unchanged. Detailed test outcomes (PASSED/FAILED/SKIPPED/NOT_RUN) are retained below.

| ID | Original requirement | Status | Code / actual verification |
|---|---|---|---|
| I01 | Инвойс не создаёт банковское поступление самим фактом загрузки. | VERIFIED | ingestion.snapshot; T021; artifacts/regression-agent-data-v3.json |
| I02 | Договорная дата, прогнозная дата и фактическая дата оплаты — разные поля. | VERIFIED | compute.obligation_flows / ingestion.snapshot; T021, T024, T025; artifacts/regression-agent-data-v3.json |
| I03 | Запрошенная отсрочка не меняет обязательство без подтверждения. | VERIFIED | contingency.request_extension / observe_decisions; T043, T051; artifacts/regression-agent-data-v3.json |
| I04 | Заявка или предварительно подходящий продукт не увеличивают остаток. | VERIFIED | store.objects / ingestion.snapshot; T044; artifacts/regression-agent-data-v3.json |
| I05 | `SUBMITTED` и `SETTLED` — разные состояния; текст LLM не определяет успех. | VERIFIED | execution.deliver / refresh; T080, T082, T095; artifacts/regression-agent-data-v3.json |
| I06 | Повтор импорта не создаёт вторую экономическую операцию. | VERIFIED | ingestion.import_csv / store.add_fact; T002, T020; artifacts/regression-agent-data-v3.json |
| I07 | Повтор отправки той же команды не создаёт вторую логическую оплату. | VERIFIED | execution.prepare / sandbox.World.submit; T074, T075, T078; artifacts/regression-agent-data-v3.json |
| I08 | Ни одно действие не исполняется без актуальных прав и требуемого подтверждения. | VERIFIED | store.authorize / execution._approval_checks; T071, T072; artifacts/regression-agent-data-v3.json |
| I09 | Два параллельных действия не расходуют один резерв дважды. | VERIFIED | execution.prepare / BEGIN IMMEDIATE; T076; artifacts/regression-agent-data-v3.json |
| I10 | Потерянный ответ не разрешает освобождать резерв или платить заново вслепую. | VERIFIED | execution.deliver / refresh; T079, T080, T081; artifacts/regression-agent-data-v3.json |
| I11 | Суммы имеют валюту; расчёты разных валют не смешиваются без явной операции FX. | VERIFIED | domain.Money / ingestion.parse_row; T014; artifacts/regression-agent-data-v3.json |
| I12 | Деньги хранятся в минимальных единицах; нет float для денежных итогов. | VERIFIED | domain.minor / rate_charge; T014, T015; artifacts/regression-agent-data-v3.json |
| I13 | Частичная оплата уменьшает задолженность только на связанную сумму. | VERIFIED | ingestion.allocate / snapshot; T007, T025; artifacts/regression-agent-data-v3.json |
| I14 | Суммарные аллокации не превышают доступную сумму соответствующего платежа. | VERIFIED | ingestion.allocate_in_transaction; T008, T009; artifacts/regression-agent-data-v3.json |
| I15 | Неизвестное назначение платежа не убирает реальное движение денег из учёта. | VERIFIED | ingestion.snapshot / execution.refresh; T010, T011, T090; artifacts/regression-agent-data-v3.json |
| I16 | Торговая выручка и её перечисление через провайдера не считаются двумя продажами. | VERIFIED | compute.merchant_bridge; T013; artifacts/regression-agent-data-v3.json |
| I17 | Факторинговый аванс и исходное поступление не могут быть независимыми двойными доходами. | VERIFIED | compute.factoring_flows / obligation_flows; T041; artifacts/regression-agent-data-v3.json |
| I18 | Регулярный прогноз не дублирует известные конкретные обязательства. | VERIFIED | compute.forecast residual de-duplication; T022; artifacts/regression-agent-data-v3.json |
| I19 | Изменения сохраняют версии; прошлое решение воспроизводится по прошлому snapshot. | VERIFIED | store.facts / objects; T016, T017; artifacts/regression-agent-data-v3.json |
| I20 | Исторический расчёт видит только сведения, известные на момент решения. | PARTIAL | store.facts cutoff / forecast; T016, T031; artifacts/regression-agent-data-v3.json |
| I21 | Нельзя финансировать утренний платёж вечерним поступлением без допустимого механизма. | VERIFIED | compute.trajectory / validation.validate_plan; T027; artifacts/regression-agent-data-v3.json |
| I22 | Обязательства по финансированию не исчезают за концом 30-дневного экрана. | VERIFIED | compute.financing / forecast; T028, T040; artifacts/regression-agent-data-v3.json |
| I23 | Жёсткое правило нельзя обменять на снижение стоимости в целевой функции. | VERIFIED | planner.solve / validation.validate_plan; T045, T046; artifacts/regression-agent-data-v3.json |
| I24 | Скрытое будущее симулятора недоступно агенту, инструментам и retrieval. | PARTIAL | sandbox capability interface / future OS isolation; T097; artifacts/regression-agent-data-v3.json |
| I25 | `UNKNOWN` solver не равен доказанной несовместимости; `FEASIBLE` не равен доказанному оптимуму. | VERIFIED | planner.solve statuses / tests.test_planner; T047, T048; artifacts/regression-agent-data-v3.json |
| I26 | Тестовая вероятность не называется вероятностью реального банкротства без калибровки. | VERIFIED | compute.forecast provenance labels; T029, T030; artifacts/regression-agent-data-v3.json |
| I27 | Подтверждение относится к конкретной версии команды, сумме, получателю и условиям. | VERIFIED | execution.approve / _approval_checks; T059, T073; artifacts/regression-agent-data-v3.json |
| I28 | Чужая компания недоступна через API, фоновые задачи, кэш, embeddings и документы. | PARTIAL | store.authorize / evidence / API / cache; T004, T060, T061, T062, T097; artifacts/regression-agent-data-v3.json |
| I29 | Инструкция внутри документа не расширяет права агента. | VERIFIED | agents.ToolRegistry / server policy; T056, T057, T058; artifacts/regression-agent-data-v3.json |
| I30 | Модельный checkpoint не является платёжным checkpoint. | VERIFIED | execution.prepare / worker / LangGraph resume; T077, T078, T086; artifacts/regression-agent-data-v3.json |
| I31 | Исполненный платёж не откатывается удалением записи; компенсация — новая операция. | VERIFIED | immutable ledger / execution.cancel_plan; T087, T089; artifacts/regression-agent-data-v3.json |
| I32 | Недоступность LLM не ослабляет авторизацию или обязательные проверки. | VERIFIED | agents.ModelGateway / execution.approve; T066; artifacts/regression-agent-data-v3.json |
| I33 | Непроверенный внешний источник не обновляет каталог кредитов прямо в процессе платежа. | VERIFIED | compute.financing / immutable DEMO terms; T042; artifacts/regression-agent-data-v3.json |
| I34 | Результаты измерений содержат реальные значения и границы; запрещены фиктивные KPI. | VERIFIED | scripts.test / benchmark / report; T098, T099; artifacts/regression-agent-data-v3.json |
| I35 | Публичный код и публичные данные могут иметь разные лицензии. | VERIFIED | docs/data_cards / source manifest; T100; artifacts/regression-agent-data-v3.json |
| I36 | Наши внутренние резервы не гарантируют контроль операций владельца в стороннем приложении. | VERIFIED | execution.refresh / deliver funds recheck; T090, T092; artifacts/regression-agent-data-v3.json |
| T001 | корректный CSV импортируется; сумма движений согласуется с остатком. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T001_balanced_import |
| T002 | повтор того же файла не меняет balances/обязательства второй раз. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T002_file_repeat |
| T003 | одинаковые external IDs у разных providers не склеиваются. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T003_provider_namespaces |
| T004 | одинаковые IDs у разных tenants не создают cross-tenant связи. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T004_tenant_namespaces |
| T005 | повреждённая строка попадает в quarantine с причиной, остальные обрабатываются по политике. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T005_quarantine |
| T006 | неизвестная схема возвращает UNSUPPORTED_SCHEMA, без ложного success. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T006_unsupported_schema |
| T007 | частичная оплата уменьшает outstanding только на фактическую сумму. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T007_partial_allocation |
| T008 | один платёж может корректно закрыть несколько обязательств. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T008_one_payment_many |
| T009 | сумма allocations не превышает сумму платежа. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T009_overallocation |
| T010 | переплата остаётся явным credit/unallocated balance, а не исчезает. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T010_overpayment_preserved |
| T011 | unmatched transaction сохраняется в cash history. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T011_unmatched_cash |
| T012 | corrected/red invoice связывается с исходником и не дублирует деньги. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T012_red_invoice_link |
| T013 | commission/refund/settlement считаются согласованно, без двойной выручки. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T013_merchant_bridge |
| T014 | разные валюты не складываются как одна сумма. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T014_currency_and_integer |
| T015 | округление fees и процентов воспроизводимо в minor units. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T015_rounding |
| T016 | поздно полученное событие не видно в прошлом snapshot. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T016_late_observation |
| T017 | исправление факта сохраняет прежнюю версию и evidence. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T017_version_preserved |
| T018 | неполная выписка создаёт quality flag, а не искусственную проводку. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T018_incomplete_statement |
| T019 | конфликт суммы/даты/получателя требует review критичного поля. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T019_conflict_review |
| T020 | перестановка независимых строк не меняет итоговый financial state. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T020_order_independence |
| T021 | invoice_date не создаёт cash receipt до фактической/сценарной оплаты. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T021_invoice_not_cash |
| T022 | обязательство и residual forecast не учитываются дважды. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T022_residual_deduplication |
| T023 | неоплаченный счёт не исключается из обучающего survival набора как будто его нет. | MISSING (NOT_RUN) | No trained survival dataset/model in this milestone |
| T024 | прогноз overdue invoice условен на отсутствие оплаты до текущей даты. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T024_overdue_conditional_fallback |
| T025 | частичный платёж уменьшает последующее прогнозируемое поступление. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T025_partial_forecast |
| T026 | счета одного клиента получают общий сценарный shock. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T026_shared_customer_shock |
| T027 | morning payment не финансируется evening receipt того же дня. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T027_intraday_ordering |
| T028 | forecast включает repayment после основного UI-горизонта. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T028_repayment_tail |
| T029 | sparse history использует явно маркированный fallback. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T029_sparse_label |
| T030 | сценарная частота не выводится как «вероятность банкротства». | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T030_probability_label |
| T031 | временная валидация не использует признаки после cutoff. | MISSING (NOT_RUN) | No training/temporal-validation pipeline; observed cutoff is covered by T016 |
| T032 | компании holdout не попадают в обучение через invoice-level split. | MISSING (NOT_RUN) | No training/company-holdout pipeline or downloaded dataset |
| T033 | изменённый snapshot инвалидирует зависимый forecast cache. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T033_snapshot_cache_key |
| T034 | недостаток бухгалтерских данных блокирует неподтверждённый P&L. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T034_pnl_blocked |
| T035 | объяснение метрик ссылается на правильные calculation IDs. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T035_metric_evidence |
| T036 | eligibility UNKNOWN сохраняет missing fields, не становится PASS. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T036_eligibility_unknown |
| T037 | заведомое несоответствие выдаёт FAIL с источником условия. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T037_eligibility_fail |
| T038 | дешёвый продукт с поздней выдачей исключается из закрытия раннего дефицита. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T038_late_finance |
| T039 | upfront fee учитывается в чистом поступлении. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T039_net_proceeds |
| T040 | график долга включает проценты, комиссии и остаток principal. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T040_debt_schedule |
| T041 | factoring не создаёт двойного прихода от invoice и advance. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T041_factoring |
| T042 | устаревшая quote требует обновления/пересогласования. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T042_expired_quote |
| T043 | неподтверждённая extension не изменяет due_date. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T043_extension_request_not_fact |
| T044 | loan application не увеличивает current cash. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T044_application_not_cash |
| T045 | solver не нарушает protected salary ради уменьшения cost. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T045_protected_salary |
| T046 | hard reserve не превращается в soft penalty без согласия. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T046_hard_reserve |
| T047 | FEASIBLE не отображается как OPTIMAL. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T047_feasible_status |
| T048 | UNKNOWN не отображается как INFEASIBLE. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T048_unknown_status |
| T049 | независимый validator обнаруживает искусственно испорченный план. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T049_independent_corruption |
| T050 | отсутствующий допустимый план объясняет конфликт без выдуманного решения. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T050_no_plan_explained |
| T051 | contingent branch активируется только наблюдаемым подтверждением. | VERIFIED (PASSED) | tests.test_contingency.ContingencyTests.test_T051_branch_activates_only_after_observed_confirmation |
| T052 | решение не меняется от скрытого будущего при одинаковых наблюдениях. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T052_nonanticipative |
| T053 | план содержит нециклические зависимости и completion predicates. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T053_dag |
| T054 | no-debt вариант сравнивается, но не выдумывается при невозможности. | VERIFIED (PASSED) | tests.test_domain.DomainTests.test_T054_no_debt_not_invented |
| T055 | what-if меняет scenario, но не actual facts без отдельного workflow. | VERIFIED (PASSED) | tests.test_api.ApiTests.test_T055_what_if_isolated |
| T056 | неизвестное название инструмента отвергается allowlist. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T056_tool_allowlist |
| T057 | аргумент SQL/shell не исполняется как код. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T057_no_code_argument |
| T058 | prompt injection в PDF не меняет policy и tool permissions. | VERIFIED (PASSED) | tests.test_documents.DocumentTests.test_T058_pdf_injection_does_not_grant_tool_or_policy_rights |
| T059 | подмена банковских реквизитов требует новой beneficiary version и approval. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T059_beneficiary_version |
| T060 | cross-tenant API request получает отказ независимо от текста prompt. | VERIFIED (PASSED) | tests.test_api.ApiTests.test_T060_api_tenant_and_roles |
| T061 | cross-tenant retrieval не возвращает документы/embeddings. | VERIFIED (PASSED) | tests.test_agent_data.AgentDataTests.test_T061_old_workflow_evidence_is_denied_after_role_change; tests.test_execution.ExecutionTests.test_T061_scoped_retrieval |
| T062 | кэш с чужим tenant или policy scope не используется. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T062_cache_scope |
| T063 | LLM output invalid JSON проходит bounded repair или явный failure. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T063_bounded_invalid_output |
| T064 | schema-valid, но экономически неверная сумма отклоняется доменным validator. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T064_wrong_economic_amount |
| T065 | превышение call/time/cost budget завершает этап контролируемо. | VERIFIED (PASSED) | tests.test_gateway.GatewayTests.test_T065_steps_tokens_time_and_no_paid_cost_enforced; tests.test_workflows.WorkflowTests.test_T065_step_token_and_context_budgets |
| T066 | outage LLM не разрешает обход approval или policy. | VERIFIED (PASSED) | tests.test_agent_data.AgentDataTests.test_T066_T086_selected_due_action_requires_exact_approval_and_reconciles_once; tests.test_execution.ExecutionTests.test_T066_model_outage_no_bypass |
| T067 | fallback provider не получает запрещённые данные. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T067_fallback_denied |
| T068 | секреты отсутствуют в prompt, клиентском bundle и логах. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T068_no_secrets_in_outputs |
| T069 | пользовательская фраза не меняет постоянную политику без подтверждения. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T069_phrase_not_policy |
| T070 | объяснение не обещает банковское одобрение или гарантированную доходность. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T070_no_approval_promise |
| T071 | action без approval не отправляется. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T071_approval_required |
| T072 | истёкший/revoked approval не используется. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T072_revoke_and_expiry |
| T073 | изменённый payload не проходит approval hash check. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T073_payload_hash |
| T074 | тот же idempotency key и payload возвращают прежнее logical action. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T074_same_key_payload |
| T075 | тот же key и другой payload дают conflict. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T075_key_conflict |
| T076 | две параллельные команды не расходуют один бюджет дважды. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T076_parallel_reserves |
| T077 | crash после commit до dispatch не теряет outbox event. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T077_outbox_survives_restart |
| T078 | повтор outbox delivery не создаёт вторую внешнюю операцию. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T078_duplicate_delivery |
| T079 | crash после отправки до сохранения ответа восстанавливается через status lookup. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T079_crash_after_send |
| T080 | timeout переводит в UNKNOWN, не в подтверждённый FAILED. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T080_timeout_unknown |
| T081 | UNKNOWN удерживает необходимый резерв до безопасного reconciliation. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T081_unknown_keeps_reserve |
| T082 | поздний settlement закрывает резерв и ledger ровно один раз. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T082_late_settlement_once |
| T083 | повторный webhook не дублирует проводку. | VERIFIED (PASSED) | tests.test_webhook.WebhookTests.test_T083_repeated_signed_webhook_preserves_one_movement_and_ledger_pair |
| T084 | out-of-order event не откатывает SETTLED в SUBMITTED. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T084_terminal_state_not_regressed |
| T085 | provider hold и внутренний резерв не вычитаются дважды. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T085_hold_not_double_counted |
| T086 | LangGraph resume не создаёт новую логическую оплату. | VERIFIED (PASSED) | tests.test_agent_data.AgentDataTests.test_T066_T086_selected_due_action_requires_exact_approval_and_reconciles_once; tests.test_workflows.WorkflowTests.test_T086_graph_resume_exact_approval_worker_and_reconciliation |
| T087 | partial execution сохраняет проведённые действия при replan. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T087_partial_execution_preserved |
| T088 | kill switch блокирует новые sends, но позволяет читать статус и сверять. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T088_kill_switch_status_continues |
| T089 | отмена плана не притворяется отменой уже отправленного платежа. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T089_cancel_keeps_sent_action |
| T090 | операция владельца вне Copilot обнаруживается refresh/reconciliation и влияет на план. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T090_external_owner_cash |
| T091 | изменение data source приводит к новому snapshot и видимой причине пересчёта. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T091_source_changes_snapshot |
| T092 | materiality/debounce не скрывает обязательную pre-execution проверку. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T092_refresh_before_send |
| T093 | пользователь видит различие actual/scenario и confirmed/expected cash. | VERIFIED (PASSED) | tests.test_api.ApiTests.test_T093_actual_expected_api_and_ui |
| T094 | английский UI корректно отображает китайские строки, суммы и валюту. | VERIFIED (PASSED) | cua.resource_stage_ui |
| T095 | полный golden path проходит из чистого окружения без ручной правки БД. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T095_fresh_golden |
| T096 | evaluator определяет успех по WorldState, не по словам агента. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T096_evaluator_ignores_agent_text |
| T097 | агент не читает private truth files, seeds и labels. | MISSING (NOT_RUN) | Observation capability is scoped but private files are not OS/container isolated from local administrators |
| T098 | baseline/full используют одинаковые наблюдения и внешние сценарии. | VERIFIED (PASSED) | tests.test_execution.ExecutionTests.test_T098_same_world_inputs |
| T099 | отчёт различает PASSED, FAILED, SKIPPED и NOT_RUN без фиктивных значений. | VERIFIED (PASSED) | tests.test_governance.GovernanceTests.test_T099_honest_status_report |
| T100 | source/license manifest и attribution соответствуют включённым файлам и моделям. | VERIFIED (PASSED) | tests.test_governance.GovernanceTests.test_T100_source_manifest_and_dependencies |
| W01 | инвентаризировать существующий репозиторий, не уничтожая файлы и инструкции. | VERIFIED | docs/HANDOFF_INVENTORY.json; tests/test_governance.py; Original handoff hashes checked; no Git metadata |
| W02 | создать ADR для стеков, типов денег, времени и режима доступа. | VERIFIED | docs/adr/0001-local-milestone.md; docs/adr/0002-product-continuation.md; docs/adr/0003-postgresql.md; Explicit stack/money/time/access decisions |
| W03 | настроить lint/type/test/CI и lockfiles. | PARTIAL | pyproject.toml; requirements.lock; scripts/check.py; .github/workflows/ci.yml; Local checks ran; remote CI NOT_RUN |
| W04 | реализовать tenant/auth/roles и ограниченные DB roles. | PARTIAL | finance/store.py; finance/postgres.py; tests/test_postgres.py; Membership + restricted DB logins/RLS verified; worker shares tenant role |
| W05 | создать базовые entities/migrations и финансовые checks. | VERIFIED | finance/migrations; finance/postgres/001_core.sql; tests/test_domain.py; Both actual stores exercise core entities and financial checks |
| W06 | source storage, hashes и provenance. | VERIFIED | finance/store.py; finance/ingestion.py; tests/test_domain.py; Source bytes, hashes, immutable versions, observed cutoffs |
| W07 | CSV adapter и quarantine/review workflow. | VERIFIED | finance/workspace.py; finance/api.py; web/app.js; tests/test_workspace.py; CSV review correction/discard and browser review verified; fixed CSV schema scope |
| W08 | snapshots с observed/effective time. | VERIFIED | finance/ingestion.py; finance/store.py; finance/migrations/004_policy_time.sql; tests/test_policy_history.py; tests/test_postgres.py; Observed/effective fact cutoffs and historical policy selection verified; unknown legacy policy times fail historical recomputation explicitly |
| W09 | exact и partial matching с безопасным review. | PARTIAL | finance/ingestion.py; web/app.js; tests/test_domain.py; Exact/partial manual allocations verified; calibrated fuzzy matching absent |
| W10 | balances, reservations semantics и операционный ledger. | VERIFIED | finance/execution.py; finance/domain.py; tests/test_execution.py; Minor-unit balances, active reserves, provider holds, balanced settlement ledger |
| W11 | simulator world, observation API, isolated truth. | PARTIAL | sandbox/world.py; sandbox/server.py; finance/adapter.py; Separate process/DB and capability boundary verified; OS private-file isolation missing |
| W12 | golden fixtures и независимый arithmetic oracle. | VERIFIED | scripts/runtime.py; sandbox/world.py; tests/test_evaluator_deadlines.py; Fresh golden and independent cash/debt/deadline oracle verified |
| W13 | cash analytics и data-quality UI/API. | PARTIAL | finance/compute.py; finance/workspace.py; web/app.js; Cash/overdue/outstanding and quality UI verified; richer aging/concentration not implemented |
| W14 | deterministic calendar forecast F0. | VERIFIED | finance/compute.py; tests/test_domain.py; F0 deterministic calendar, money and evidence |
| W15 | scenario delays/shocks F1 и labels происхождения. | VERIFIED | finance/compute.py; finance/validation.py; tests/test_workspace.py; Uncalibrated delays, partial receipts, shared-customer shocks; no learned probabilities |
| W16 | product catalog/version/eligibility PASS-FAIL-UNKNOWN. | VERIFIED | finance/compute.py; finance/ingestion.py; tests/test_domain.py; Immutable observed DEMO catalog and PASS/FAIL/UNKNOWN screening |
| W17 | financing cashflows, fees и repayments. | VERIFIED | finance/compute.py; tests/test_domain.py; Net proceeds, charges, interest, repayment tail; execution limited to DEMO loans |
| W18 | candidate action compiler и CP-SAT model. | VERIFIED | finance/planner.py; tests/test_planner.py; Actual OR-Tools finite-grid compiler, objectives and prefix constraints; oracle comparison |
| W19 | независимый plan validator и solver statuses. | VERIFIED | finance/validation.py; tests/test_planner.py; tests/test_domain.py; Independent validation, timeout UNKNOWN, no false OPTIMAL |
| W20 | plan DAG/conditional branches/what-if. | PARTIAL | finance/contingency.py; finance/execution.py; tests/test_contingency.py; DAG, what-if and observed conditional extension verified; arbitrary branching remains |
| W21 | approval canonical payload, expiry/revocation. | VERIFIED | finance/execution.py; tests/test_execution.py; tests/test_workflows.py; Exact canonical payload/expiry/revoke and stale-command refresh tested |
| W22 | execution state machine и transaction-safe reservations. | VERIFIED | finance/execution.py; finance/worker.py; tests/test_postgres.py; Atomic reserves/outbox/jobs; SQLite and PostgreSQL concurrency tested |
| W23 | outbox/inbox, retry/status lookup, reconciliation. | VERIFIED | finance/worker.py; finance/hooks.py; tests/test_webhook.py; tests/test_execution.py; Leases/status lookup/reconciliation and HMAC internal webhook duplicates tested |
| W24 | kill switch, partial execution и safe recovery. | VERIFIED | finance/execution.py; tests/test_execution.py; Kill switch, partial execution, UNKNOWN and safe recovery |
| W25 | tool registry и типизированные errors. | VERIFIED | finance/agents.py; finance/agent_data.py; finance/workflows.py; contracts/agent-tools-v2.json; tests/test_agent_data.py; Typed scoped business readers, full calculations, what-if, selected action and conditional extension proposals; no send/approve/shell/SQL |
| W26 | LangGraph workflow с bounded retries и resume safety. | PARTIAL | finance/workflows.py; tests/test_agent_data.py; tests/test_workflows.py; tests/test_postgres.py; Persistent LangGraph with exact visible record/plan/action pairs, selected-action replan, mandatory separate approval and single-action reconciliation; expanded live verification tracked separately from historical 8/10 baselines |
| W27 | ModelGateway mock/live, costs, privacy и fallback. | PARTIAL | finance/gateway.py; tests/test_gateway.py; scripts/local_llm.py; scripts/resource_guard.py; scripts/live_compare.py; Expanded Qwen14B local evaluation:20 distinct cases/21 attempts,8 strict passes; assistant review6 complete/5 partial/7 failed/2 RAM-interrupted scenarios. Q8/Q4 cache profiles separate; guards retained. Supplementary browser cash/date correct but source ID mislabelled. Historical7B/8B scores not comparable. See LOCAL_14B_RESULTS.md |
| W28 | source retrieval/evidence graph и report formatter. | PARTIAL | finance/workspace.py; finance/store.py; tests/test_documents.py; ACL/version/source retrieval and report links verified; semantic retrieval/evidence benchmark absent |
| W29 | полноценный английский UI для main flow. | PARTIAL | web/index.html; web/app.js; web/style.css; artifacts/browser-smoke.json; Ten functional routes and browser flows verified; standalone E2E runner/accessibility matrix absent |
| W30 | ingestion/doc parsing P1 после стабильного CSV. | PARTIAL | finance/parser.py; finance/workspace.py; tests/test_documents.py; Text PDF extraction/indexing/injection test verified; OFD/XML/OCR/OS parser isolation absent |
| W31 | event-driven replan/materiality/notifications. | PARTIAL | finance/contingency.py; finance/workflows.py; finance/execution.py; Observed event replan and send rechecks verified; generalized debounce/internal alerts absent |
| W32 | T001–T100 automation и дополнительные property/race cases. | PARTIAL | scripts/test.py; tests; artifacts/regression-agent-data-v3.json; T001–T100 tracked; unresolved targets stay NOT_RUN; no blanket completion claim |
| W33 | baseline/ablation runs с независимым evaluator. | PARTIAL | scripts/benchmark.py; artifacts/benchmark.json; Three paired deterministic sensitivity runs; diverse synthetic/live B1/B2/B3 absent |
| W34 | model/data cards, license inventory и security self-assessment. | PARTIAL | docs/data_cards/synthetic.md; docs/model_cards/local-gateway.md; scripts/licenses.py; docs/SECURITY.md; Actual metadata inventory; source rights/real model licenses not inferred |
| W35 | English README, architecture, demo script, runbooks и packaging. | VERIFIED | README.md; docs/architecture/README.md; docs/runbooks; docs/submission/demo-script.md; English runnable instructions and boundaries updated; final contest media outside product deliverable |
| W36 | fresh environment rehearsal, actual results report и release tag. | PARTIAL | scripts/rehearse.py; artifacts/rehearsal.json; Fresh code/venv/wheels/DB golden verified; no Git repository/release tag/remote CI |

Live provider/novel-task evidence and its limits: docs/model_cards/local-gateway.md. Connectivity, structural task outcomes and narrative quality are separate claims.
Full private-truth OS isolation: MISSING. Full-product overall gate: PARTIAL. See KNOWN_LIMITATIONS.md.
