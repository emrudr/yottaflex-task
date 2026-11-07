# Pipeline Determinism & Reproducibility Audit

**Audit Status:** `PASS`

This report compares identical consecutive pipeline executions across independent runs using fixed random seeds without timestamps or wall-clock dependencies.

| File Path | Run A Rows | Run B Rows | Checksum Status |
|---|---|---|---|
| `data/account_devices.csv` | 7296 | 7296 | `IDENTICAL` |
| `data/account_status_events.csv` | 7257 | 7257 | `IDENTICAL` |
| `data/accounts.csv` | 7001 | 7001 | `IDENTICAL` |
| `data/alert_evidence.csv` | 2669 | 2669 | `IDENTICAL` |
| `data/alert_score_components.csv` | 2599 | 2599 | `IDENTICAL` |
| `data/alerts.csv` | 1019 | 1019 | `IDENTICAL` |
| `data/analyst_actions.csv` | 3163 | 3163 | `IDENTICAL` |
| `data/analysts.csv` | 13 | 13 | `IDENTICAL` |
| `data/cases.csv` | 719 | 719 | `IDENTICAL` |
| `data/customers.csv` | 5001 | 5001 | `IDENTICAL` |
| `data/devices.csv` | 7016 | 7016 | `IDENTICAL` |
| `data/merchants.csv` | 601 | 601 | `IDENTICAL` |
| `data/risk_rules.csv` | 8 | 8 | `IDENTICAL` |
| `data/source_manifest.json` | 30 | 30 | `IDENTICAL` |
| `data/transactions.csv` | 100001 | 100001 | `IDENTICAL` |
| `data/transfer_links.csv` | 1643 | 1643 | `IDENTICAL` |
| `ground_truth/ground_truth.csv` | 739 | 739 | `IDENTICAL` |
| `ground_truth/ground_truth.json` | 11072 | 11072 | `IDENTICAL` |
| `sql/seed.sql` | 146237 | 146237 | `IDENTICAL` |
| `reports/alert_ranking.csv` | 1019 | 1019 | `IDENTICAL` |
| `reports/validation_results.json` | 65 | 65 | `IDENTICAL` |
| `reports/validation_summary.md` | 62 | 62 | `IDENTICAL` |
