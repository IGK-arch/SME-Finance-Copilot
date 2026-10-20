# Design sources

Research inputs used while designing the product. They are **not** loaded into the
application or into the model context, and no dataset listed in them was downloaded
or used for training or runtime (see [data card](../docs/data_cards/synthetic.md)).

| ID | Document | Origin | How it informed the design |
|---|---|---|---|
| R1 | `R1_rules.md` / `.docx` | Competition organiser: International Track topics and rules | Topic E scope, submission items and scoring criteria |
| R2 | `R2_datasets.md` / `.docx` | Team research: survey of public datasets and data sources (SME invoices, credit scoring, transactions, documents) with links and licence notes; LPR as a reference rate | Choice of a synthetic data model; no external dataset is used |
| R3 | `R3_china_research.md` / `.docx`, `assets/R3_image1.png` | Team research (10 Oct 2026): competitor stacks, data pipeline and Chinese SME-finance regulation (PBoC credit-information rules) | Compliance boundaries (no credit scoring or lender approval claims), financing-cost model, MVP stack |

`manifest.json` records the original file names, SHA-256 hashes and every hyperlink
(the public URLs cited by R2 and R3). Statements in these documents are kept as
written by their authors and were not re-verified for this submission.
