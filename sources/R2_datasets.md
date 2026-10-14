# R2. Исходный документ: SME_Copilot_datasets_links.docx

Источник перенесён без редакторского изменения утверждений. Сохранены исходные оговорки; статусы проверки принадлежат автору исходника. Для точной исходной вёрстки, таблиц и иллюстраций см. приложенный DOCX. Гиперссылки раскрыты в текст.

SME Finance Copilot (Topic E) ссылки на датасеты и источники данных

1. Датасеты

Группы данных: A — транзакции, B — фискальные и документы, G — альтернативные и опросные, H — кредит и скоринг, I / LLM — внешний контекст и текстовые корпуса. D1–D4 — датасеты MVP-набора.

**Поля таблицы:** № | Датасет | Группа | Тип данных | Лицензия | Статус проверки | Роль в MVP | Ссылка

**Запись 1.**
- №: 1
- Датасет: CUMCM 2020, задача C «中小微企业的信贷决策» (инвойсы МСП + кредитные рейтинги)
- Группа: B / H
- Тип данных: Анонимизированные; train
- Лицензия: Не указана
- Статус проверки: ◐ Частично: официальной страницы данных нет; подтверждено статьёй и описанием
- Роль в MVP: D1 — train модели готовности, калибровка генератора
- Ссылка: https://www.atlantis-press.com/article/125977116.pdf

**Запись 2.**
- №: 2
- Датасет: CUMCM 2020 C — описание задачи и данных (CSDN, 25.05.2021)
- Группа: B / H
- Тип данных: —
- Лицензия: —
- Статус проверки: ✓ Открыта
- Роль в MVP: Справка к D1
- Ссылка: https://damodev.csdn.net/6a4331f510ee7a33f284496b.html

**Запись 3.**
- №: 3
- Датасет: Tianchi «零基础入门金融风控-贷款违约预测» (дефолты кредитов)
- Группа: H
- Тип данных: Анонимизированные; train; 2020
- Лицензия: Не указана
- Статус проверки: ✓ Метаданные
- Роль в MVP: D2 — baseline скоринга
- Ссылка: https://tianchi.aliyun.com/competition/entrance/531830/information

**Запись 4.**
- №: 4
- Датасет: CFLUE (Alibaba Cloud)
- Группа: I / LLM
- Тип данных: Реальные экзаменационные вопросы; benchmark + train-часть
- Лицензия: Код MIT; данные CC BY-NC-SA 4.0
- Статус проверки: ✓ Открыта
- Роль в MVP: D3 — LoRA и оценка
- Ссылка: https://github.com/aliyun/cflue

**Запись 5.**
- №: 5
- Датасет: PaddleOCR — ключевые поля инвойса НДС (doc v2.9)
- Группа: B
- Тип данных: Реальные изображения; 38 шт.
- Лицензия: Не указана
- Статус проверки: ✓ Открыта
- Роль в MVP: D4 — тест OCR
- Ссылка: https://www.paddleocr.ai/v2.9/applications/%E5%8F%91%E7%A5%A8%E5%85%B3%E9%94%AE%E4%BF%A1%E6%81%AF%E6%8A%BD%E5%8F%96.html [https://www.paddleocr.ai/v2.9/applications/发票关键信息抽取.html]

**Запись 6.**
- №: 6
- Датасет: Baidu AI Studio, датасет 165561 (файлы для D4)
- Группа: B
- Тип данных: Реальные изображения
- Лицензия: Не указана
- Статус проверки: ◐ Ссылка из документации PaddleOCR, напрямую не проверена
- Роль в MVP: D4 — скачивание
- Ссылка: https://aistudio.baidu.com/aistudio/datasetdetail/165561

**Запись 7.**
- №: 7
- Датасет: Home Credit Default Risk (Kaggle, 2018)
- Группа: H
- Тип данных: Анонимизированные; train; классика
- Лицензия: Не указана (правила Kaggle)
- Статус проверки: ✓ Метаданные
- Роль в MVP: Резерв для D2
- Ссылка: https://www.kaggle.com/c/home-credit-default-risk/data

**Запись 8.**
- №: 8
- Датасет: Home Credit Default Risk — зеркало IEEE DataPort
- Группа: H
- Тип данных: Анонимизированные
- Лицензия: По подписке
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://ieee-dataport.org/documents/home-credit-default-risk

**Запись 9.**
- №: 9
- Датасет: Give Me Some Credit (Kaggle, 2011)
- Группа: H
- Тип данных: Анонимизированные; train; классика
- Лицензия: Не указана
- Статус проверки: ◐ Kaggle напрямую не проверен; подтверждено через empulse/OpenML
- Роль в MVP: —
- Ссылка: https://www.kaggle.com/c/GiveMeSomeCredit/data

**Запись 10.**
- №: 10
- Датасет: Give Me Some Credit — OpenML
- Группа: H
- Тип данных: Анонимизированные
- Лицензия: Не указана
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://api.openml.org/d/45024

**Запись 11.**
- №: 11
- Датасет: Berka / PKDD’99 Financial (Czech Financial Dataset)
- Группа: A
- Тип данных: Анонимизированные; train; классика 1999
- Лицензия: Не указана
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://relational.fel.cvut.cz/dataset/Financial

**Запись 12.**
- №: 12
- Датасет: PaySim (синтетика mobile money)
- Группа: A
- Тип данных: Синтетические; train
- Лицензия: Не подтверждена
- Статус проверки: ✓ Метаданные
- Роль в MVP: —
- Ссылка: https://www.kaggle.com/datasets/ealaxi/paysim1

**Запись 13.**
- №: 13
- Датасет: PaySim — зеркало на GitHub
- Группа: A
- Тип данных: Синтетические
- Лицензия: Не подтверждена
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://github.com/BBQtime/Synthetic-Financial-Datasets-For-Fraud-Detection

**Запись 14.**
- №: 14
- Датасет: IBM TabFormer (24 млн синтетических транзакций)
- Группа: A
- Тип данных: Синтетические; train; stale
- Лицензия: Репозиторий Apache-2.0
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://github.com/IBM/TabFormer

**Запись 15.**
- №: 15
- Датасет: XFUND (формы, есть китайская часть)
- Группа: B
- Тип данных: Реальные формы; benchmark + train
- Лицензия: CC BY-NC-SA 4.0
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://github.com/doc-analysis/XFUND

**Запись 16.**
- №: 16
- Датасет: CORD (чеки, Индонезия)
- Группа: B
- Тип данных: Реальные; stale
- Лицензия: CC BY 4.0
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://github.com/clovaai/cord

**Запись 17.**
- №: 17
- Датасет: SROIE (ICDAR 2019, чеки)
- Группа: B
- Тип данных: Реальные; benchmark
- Лицензия: Не указана
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://rrc.cvc.uab.es/?ch=13

**Запись 18.**
- №: 18
- Датасет: EATEN (Baidu: билеты, паспорта, визитки)
- Группа: B
- Тип данных: Синтетика + ~2 тыс. реальных; stale
- Лицензия: Не указана
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://github.com/beacandler/EATEN

**Запись 19.**
- №: 19
- Датасет: World Bank Enterprise Survey, China 2024
- Группа: G
- Тип данных: Анонимизированные микроданные опроса
- Лицензия: Условия World Bank, ссылка обязательна
- Статус проверки: ✓ Открыта
- Роль в MVP: Распределения для генераторов M1
- Ссылка: https://microdata.worldbank.org/catalog/6676

**Запись 20.**
- №: 20
- Датасет: FinEval (SUFE)
- Группа: I / LLM
- Тип данных: Реальные; только benchmark
- Лицензия: Apache-2.0
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://github.com/SUFE-AIFLM-Lab/FinEval

**Запись 21.**
- №: 21
- Датасет: FinCorpus (Du Xiaoman), 21.2 GB
- Группа: I / LLM
- Тип данных: Реальные публичные тексты; train
- Лицензия: Apache-2.0
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://huggingface.co/datasets/Duxiaoman-DI/FinCorpus

**Запись 22.**
- №: 22
- Датасет: XuanYuan / FinanceIQ (Du Xiaoman)
- Группа: I / LLM
- Тип данных: Реальные; benchmark
- Лицензия: Не указана
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://github.com/Duxiaoman-DI/XuanYuan

**Запись 23.**
- №: 23
- Датасет: DISC-FinLLM (Fudan) — опубликован только образец SFT
- Группа: I / LLM
- Тип данных: Образец + eval; stale
- Лицензия: Проект Apache-2.0
- Статус проверки: ✓ Открыта
- Роль в MVP: Не использовать вместо CFLUE
- Ссылка: https://github.com/FudanDISC/DISC-FinLLM

**Запись 24.**
- №: 24
- Датасет: DISC-FIN-SFT — неофициальная копия на HF
- Группа: I / LLM
- Тип данных: —
- Лицензия: Не указана
- Статус проверки: ✓ Открыта (viewer не работает)
- Роль в MVP: Не использовать
- Ссылка: https://huggingface.co/datasets/eggbiscuit/DISC-FIN-SFT

**Запись 25.**
- №: 25
- Датасет: BBT-FinCorpus / FinCUGE (~300 GB)
- Группа: I / LLM
- Тип данных: Реальные; train + benchmark; stale
- Лицензия: Не указана; доступ по заявке
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://github.com/ssymmetry/BBT-FinCUGE-Applications

**Запись 26.**
- №: 26
- Датасет: FinGPT (китайская часть fingpt-fineval)
- Группа: I / LLM
- Тип данных: Реальные; stale
- Лицензия: Не указана
- Статус проверки: ✓ Открыта
- Роль в MVP: —
- Ссылка: https://github.com/AI4Finance-Foundation/FinGPT

**Запись 27.**
- №: 27
- Датасет: DISC-LawLLM / DISC-Law-SFT (~295k)
- Группа: I / LLM
- Тип данных: Смешанные; train
- Лицензия: Не указана
- Статус проверки: ✓ Открыта
- Роль в MVP: Опционально для RAG
- Ссылка: https://github.com/FudanDISC/DISC-LawLLM

2. Схемы данных и инструменты генерации синтетики

Открытых датасетов по выпискам 对公, реальным 数电票, merchant-выгрузкам и 征信 нет. Генераторы M1–M3 строятся по этим опубликованным схемам.

**Поля таблицы:** № | Источник | Для чего | Ссылка

**Запись 1.**
- №: 1
- Источник: 数电票: реквизиты и формат номера (STA 公告2024年第11号, 12.11.2024)
- Для чего: Схема для генератора инвойсов (M2)
- Ссылка: https://fgk.chinatax.gov.cn/zcfgk/c100012/c5236067/content.html

**Запись 2.**
- №: 2
- Источник: 数电票: форматы XML / PDF / OFD (新浪财经, 12.11.2024)
- Для чего: Форматы вывода M2
- Ссылка: https://finance.sina.cn/2024-11-12/detail-incvvkfz9333061.d.html

**Запись 3.**
- №: 3
- Источник: Alipay: выгрузка счетов, 24 колонки CSV (Tencent Cloud, 24.06.2022)
- Для чего: Схема платежей (M2)
- Ссылка: https://cloud.tencent.com/developer/article/2029243

**Запись 4.**
- №: 4
- Источник: WeChat Pay API v3: счёт предприятия trade-bill (09.05.2025)
- Для чего: Правила выгрузки (M2)
- Ссылка: https://pay.weixin.qq.com/doc/v3/partner/4014507142

**Запись 5.**
- №: 5
- Источник: Tianyancha API 1116: поля компании (Huawei Cloud, 23.04.2024)
- Для чего: Схема профиля компании (M1)
- Ссылка: https://support.huaweicloud.com/tbis-dma/tbis_04.html

**Запись 6.**
- №: 6
- Источник: 企业信息公示暂行条例 (2014): показатели годового отчёта, ст. 9
- Для чего: Схема отчётности (M1)
- Ссылка: https://www.gov.cn/zhengce/2014-08/23/content_2739774.htm

**Запись 7.**
- №: 7
- Источник: Кредитный отчёт: состав разделов (人民日报, 20.05.2024)
- Для чего: Структура «упрощённого 征信» (M3)
- Ссылка: https://paper.people.com.cn/rmrbwap/html/2024-05/20/nw.D110000renmrb_20240520_1-02.htm

**Запись 8.**
- №: 8
- Источник: LPR на 20.09.2026 (同花顺)
- Для чего: Внешний контекст для матчинга
- Ссылка: https://news.10jqka.com.cn/20260920/c680091504.shtml

**Запись 9.**
- №: 9
- Источник: Faker, локаль zh_CN (v40.43.0)
- Для чего: Генератор названий, адресов, банков
- Ссылка: https://faker.readthedocs.io/en/master/locales/zh_CN.html

**Запись 10.**
- №: 10
- Источник: SDV 1.37.3 (PyPI, 02.07.2026), лицензия BUSL-1.1
- Для чего: Синтез табличных и последовательных данных
- Ссылка: https://pypi.org/project/sdv/1.37.3/

## Ссылки, сохранённые в исходном DOCX

1. https://www.atlantis-press.com/article/125977116.pdf
2. https://damodev.csdn.net/6a4331f510ee7a33f284496b.html
3. https://tianchi.aliyun.com/competition/entrance/531830/information
4. https://github.com/aliyun/cflue
5. https://www.paddleocr.ai/v2.9/applications/发票关键信息抽取.html
6. https://aistudio.baidu.com/aistudio/datasetdetail/165561
7. https://www.kaggle.com/c/home-credit-default-risk/data
8. https://ieee-dataport.org/documents/home-credit-default-risk
9. https://www.kaggle.com/c/GiveMeSomeCredit/data
10. https://api.openml.org/d/45024
11. https://relational.fel.cvut.cz/dataset/Financial
12. https://www.kaggle.com/datasets/ealaxi/paysim1
13. https://github.com/BBQtime/Synthetic-Financial-Datasets-For-Fraud-Detection
14. https://github.com/IBM/TabFormer
15. https://github.com/doc-analysis/XFUND
16. https://github.com/clovaai/cord
17. https://rrc.cvc.uab.es/?ch=13
18. https://github.com/beacandler/EATEN
19. https://microdata.worldbank.org/catalog/6676
20. https://github.com/SUFE-AIFLM-Lab/FinEval
21. https://huggingface.co/datasets/Duxiaoman-DI/FinCorpus
22. https://github.com/Duxiaoman-DI/XuanYuan
23. https://github.com/FudanDISC/DISC-FinLLM
24. https://huggingface.co/datasets/eggbiscuit/DISC-FIN-SFT
25. https://github.com/ssymmetry/BBT-FinCUGE-Applications
26. https://github.com/AI4Finance-Foundation/FinGPT
27. https://github.com/FudanDISC/DISC-LawLLM
28. https://fgk.chinatax.gov.cn/zcfgk/c100012/c5236067/content.html
29. https://finance.sina.cn/2024-11-12/detail-incvvkfz9333061.d.html
30. https://cloud.tencent.com/developer/article/2029243
31. https://pay.weixin.qq.com/doc/v3/partner/4014507142
32. https://support.huaweicloud.com/tbis-dma/tbis_04.html
33. https://www.gov.cn/zhengce/2014-08/23/content_2739774.htm
34. https://paper.people.com.cn/rmrbwap/html/2024-05/20/nw.D110000renmrb_20240520_1-02.htm
35. https://news.10jqka.com.cn/20260920/c680091504.shtml
36. https://faker.readthedocs.io/en/master/locales/zh_CN.html
37. https://pypi.org/project/sdv/1.37.3/