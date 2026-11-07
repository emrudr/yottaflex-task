# Synthetic Risk-Alert Prioritization Pipeline

A deterministic, interview-explainable synthetic banking data generator and risk-alert prioritization engine. Built strictly in Python 3.10+ using `pandas`, `numpy`, and standard library components without external network or service dependencies.

---

## 1. Purpose & Business Problem

Financial institutions process massive transaction volumes where suspicious activities (e.g. rapid debit bursts, unauthorized new hardware access, circular fund routing, dormant account draining, and statistical transaction outliers) are buried under normal customer operations. Operations analysts are easily overwhelmed by unprioritized alert queues and false positives.

This pipeline delivers an automated, transparent solution:
1. **Stage 1 (Generate):** Creates a rich, synthetic banking universe (customers, accounts, devices, merchants, transactions, and transfer links) seeded with realistic operational behavior, planted suspicious patterns (`TRUE_*`), benign look-alikes (`FP_*`), and labelled data quality anomalies.
2. **Stage 2 (Detect & Prioritize):** A transparent rules engine evaluates strictly observable dataset features (with zero access to ground truth), scores alerts with full explainability, clusters correlated alerts into cases via union-find, and simulates human analyst triage and escalation workflows.
3. **Stage 3 (Validate):** Audits structural constraints (PK, FK, enums, temporal ordering, ledger math, lifecycle states), checks detection recall against isolated ground truth, verifies exact detection of injected edge cases, and enforces bit-for-bit reproducibility.

---

## 2. Quick Start & How to Run

### Installation
```bash
pip install -r requirements.txt
```

### Execution Commands

Run the entire pipeline on the **Starter Preset** (5,000 transactions, 350 accounts, 250 customers):
```bash
python run_all.py --scale starter --out output
```

Run the entire pipeline on the **Full Production Preset** (100,000 transactions, 7,000 accounts, 5,000 customers):
```bash
python run_all.py --scale full --out output
```

Verify bit-for-bit **Deterministic Reproducibility** (runs dual independent executions and checks SHA-256 hashes):
```bash
python check_reproducibility.py --scale starter --out output
python check_reproducibility.py --scale full --out output
```

---

## 3. The 5 Detection Rules & Adjustments

Detection thresholds are fully config-driven via `risk_rules.csv`:

| Rule ID | Canonical Name | Base Points | Trigger Condition | Bonuses Available |
|---|---|---|---|---|
| **R01** | `VELOCITY_SPIKE` | 60 | $\ge 6$ debits within a rolling 60-minute window | $\ge 10$ debits (+15), total amount $\ge ₹50,000$ (+15) |
| **R02** | `NEW_DEVICE_ACTIVITY` | 55 | First use of device on account, debit $\ge ₹15,000$, $\ge 5$ prior txns | Amount $\ge ₹50,000$ (+15), emulator or shared by $\ge 3$ accounts (+15) |
| **R03** | `CIRCULAR_TRANSFER` | 60 | 2–5 transfer cycle returning funds to origin within 72 hours (legs $\ge ₹5,000$) | $\ge 3$ distinct customers (+20), capital retention $\ge 90\%$ (+15) |
| **R04** | `DORMANT_REACTIVATION` | 55 | First transaction (either direction) $\ge ₹10,000$ after gap $\ge 180$ days | Debit drain $\ge 80\%$ of balance (+25), new hardware device (+15) |
| **R05** | `AMOUNT_OUTLIER` | 45 | Debit $\ge ₹25,000$ and $\ge 8\times$ median of prior debits (min 5 prior debits) | Outlier multiplier $\ge 15\times$ median (+15), HIGH-risk merchant (+10) |

### Mitigating Adjustments
- **`A01` (`SAME_OWNER_TRANSFER`, -40 pts):** Applied to `R03` circular transfers when all participating accounts belong to the same customer.
- **`A02` (`TRUSTED_CUSTOMER`, -15 pts):** Applied to any rule when the customer has tenure $\ge 3$ years, verified KYC, and low risk tier.

Scores are clamped to $[5, 100]$. Severity bands: $\ge 85 \to$ `CRITICAL`, $70..84 \to$ `HIGH`, $50..69 \to$ `MEDIUM`, $< 50 \to$ `LOW`.

---

## 4. Output Folder Structure

All artifacts are written to `output/`:
```
output/
├── data/                            # Relational tables in CSV format
│   ├── customers.csv
│   ├── accounts.csv
│   ├── account_status_events.csv    # Append-only account lifecycle journal
│   ├── devices.csv
│   ├── account_devices.csv          # N:M account-device interaction bridge
│   ├── merchants.csv
│   ├── transactions.csv             # Reconciled debit/credit ledger
│   ├── transfer_links.csv           # Bilateral transfer linkages
│   ├── risk_rules.csv               # Config-driven rules catalog
│   ├── alerts.csv                   # Synthesized risk alerts
│   ├── alert_evidence.csv           # N:M alert-transaction evidence bridge
│   ├── alert_score_components.csv   # Additive explainability breakdown
│   ├── cases.csv                    # Cases clustering alerts within 7 days
│   ├── analysts.csv                 # Personnel directory
│   ├── analyst_actions.csv          # Audit trail of triage/review actions
│   └── source_manifest.json         # SHA-256 metadata manifest
├── ground_truth/                    # Isolated ground truth datasets
│   ├── ground_truth.csv
│   └── ground_truth.json
├── sql/
│   └── seed.sql                     # Full SQLite DDL + INSERT statements
└── reports/                         # Summary and audit reports
    ├── alert_ranking.csv            # Prioritized alert queue with narratives
    ├── validation_summary.md        # Quality gates, recall & performance report
    ├── validation_results.json      # Machine-readable validation findings
    └── reproducibility.md           # Dual-run cryptographic comparison audit
```

---

## 5. How to Read `validation_summary.md`

`output/reports/validation_summary.md` summarizes the health and accuracy of the pipeline:
1. **Acceptance Gates:** Displays `PASS`/`FAIL` across 5 quality criteria:
   - *Gate 1:* Zero unexpected structural/ledger failures.
   - *Gate 2:* Injected data quality edge cases found exactly as planted.
   - *Gate 3:* Recall $\ge 95\%$ across all planted suspicious scenarios.
   - *Gate 4:* Alert volume within $\pm 10\%$ target with $\ge 20\%$ false positive representation.
   - *Gate 5:* Zero ground truth leakage into operational tables.
2. **Detection Recall by Planted Scenario:** Breakdown of true suspicious patterns detected versus expected.
3. **Labelled Injected Data Quality Anomalies:** Reconciles planted vs. independently found counts for the 5 synthetic edge cases.
4. **Key Prioritization & Performance Metrics:** High-level metrics on alert counts, false-positive representation, precision@50/100/250, and analyst disposition agreement.
