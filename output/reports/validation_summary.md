# Pipeline Validation Summary Report
**Scale Preset:** `full` | **Audit Status:** `PASS`

## 1. Acceptance Gates

| Gate | Status | Condition |
|---|---|---|
| **Gate 1: Zero Unexpected Structural Failures** | `PASS` | Verified against schema & ground truth |
| **Gate 2: Injected Anomalies Found Exactly as Planted** | `PASS` | Verified against schema & ground truth |
| **Gate 3: Detection Recall >= 0.95 for All TRUE Types** | `PASS` | Verified against schema & ground truth |
| **Gate 4: Alert Target & FP Representation (>=20%)** | `PASS` | Verified against schema & ground truth |
| **Gate 5: Zero Ground Truth Leakage** | `PASS` | Verified against schema & ground truth |

## 2. Detection Recall by Planted Scenario

| Scenario Type | Planted Scenarios | Detected Alerts | Recall Rate | Status |
|---|---|---|---|---|
| `TRUE_CIRCULAR` | 40 | 40 | 100.0% | `PASS` |
| `TRUE_DORMANT` | 85 | 85 | 100.0% | `PASS` |
| `TRUE_NEW_DEVICE` | 130 | 130 | 100.0% | `PASS` |
| `TRUE_OUTLIER` | 90 | 90 | 100.0% | `PASS` |
| `TRUE_VELOCITY` | 130 | 130 | 100.0% | `PASS` |

## 3. Labelled Injected Data Quality Anomalies

| Anomaly Issue Type | Planted Count | Detected Independently | Status |
|---|---|---|---|
| `ALERT_NO_TRIGGER` | 5 | 5 | `MATCH` |
| `DISPOSITION_BEFORE_ALERT` | 5 | 5 | `MATCH` |
| `NEGATIVE_BALANCE_NO_OD` | 10 | 10 | `MATCH` |
| `TRANSFER_LEG_MISMATCH` | 10 | 10 | `MATCH` |
| `TXN_ON_CLOSED_ACCOUNT` | 10 | 10 | `MATCH` |

## 4. Key Prioritization & Performance Metrics

- **Baseline Alerts (excluding injected):** 1008
- **False-Positive Mapped Alerts:** 223 (22.1%)
- **FP Closed as False Positive:** 100.0%
- **Disposition Agreement with Ground Truth:** 100.0%
- **Unmapped Alerts:** 0
- **Precision@50:** 100.0%
- **Precision@100:** 100.0%
- **Precision@250:** 100.0%

### Alert Distribution by Primary Rule

| Rule ID | Alert Count |
|---|---|
| `R05` | 315 |
| `R02` | 295 |
| `R01` | 215 |
| `R04` | 123 |
| `R03` | 70 |

### Alert Distribution by Severity

| Severity Band | Alert Count |
|---|---|
| `CRITICAL` | 407 |
| `LOW` | 233 |
| `MEDIUM` | 220 |
| `HIGH` | 158 |
