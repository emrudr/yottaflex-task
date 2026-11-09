# Synthetic Risk-Alert Prioritization Pipeline

This project generates synthetic banking data, finds suspicious patterns with simple rules, groups alerts into cases, and checks its own output. It creates realistic customer and transaction tables without using real personal data. It then prioritizes transactions and linked accounts for analyst review and confirms that balances and relationships reconcile.

## Requirements

- Python 3.10 or newer
- Dependencies listed in `requirements.txt`: `pandas` and `numpy`
- No internet access, server, or external database is needed. All data is stored in CSV files and verified using Python standard library SQLite.

## Install Steps

```bash
pip install -r requirements.txt
```

## How to Run

Run the starter dataset (5,000 transactions, 350 accounts, 250 customers):
```bash
python run_all.py --scale starter --out output
```

Run the full dataset (100,000 transactions, 7,000 accounts, 5,000 customers):
```bash
python run_all.py --scale full --out output
```

Run the reproducibility check (runs two independent executions and compares checksums):
```bash
python check_reproducibility.py --scale starter --out output
python check_reproducibility.py --scale full --out output
```

## What Gets Produced

All outputs are written into the `output` folder:

- `output/data/`: Core CSV tables (`customers.csv`, `accounts.csv`, `account_status_events.csv`, `devices.csv`, `account_devices.csv`, `merchants.csv`, `transactions.csv`, `transfer_links.csv`, `risk_rules.csv`, `alerts.csv`, `alert_evidence.csv`, `alert_score_components.csv`, `cases.csv`, `analysts.csv`, `analyst_actions.csv`) and `source_manifest.json`.
- `output/ground_truth/`: `ground_truth.csv` and `ground_truth.json` containing labels for planted scenarios and injected problems.
- `output/sql/`: `seed.sql` containing SQLite table definitions and insert statements.
- `output/reports/`: `alert_ranking.csv` (the prioritized queue), `validation_summary.md`, `validation_results.json`, and `reproducibility.md`.

## Where to Read More

For a full guide to the code, rules, entity relationships, verification steps, and limits, see [docs/REPO_GUIDE.md](docs/REPO_GUIDE.md).
