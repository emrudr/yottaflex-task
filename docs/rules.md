# Risk Rules Catalog & Thresholds

This document is auto-generated from `risk_rules.csv`. All rules are config-driven and evaluate strictly over observable dataset features without access to ground truth.

| Rule ID | Rule Name | Type | Base Points | Description | Parameters |
|---|---|---|---|---|---|
| `A01` | **SAME_OWNER_TRANSFER** | ADJUSTMENT | -40 | All accounts in circular transfer path are owned by the same customer | • `match_owner_scope`: ALL_ACCOUNTS |
| `A02` | **TRUSTED_CUSTOMER** | ADJUSTMENT | -15 | Customer has verified KYC, low risk tier, and tenure of at least 3 years | • `min_tenure_years`: 3<br>• `required_kyc_status`: VERIFIED<br>• `required_kyc_tier`: LOW |
| `R01` | **VELOCITY_SPIKE** | DETECTION | 60 | High volume of debit transactions within a 60-minute window | • `bonus_amount_points`: 15<br>• `bonus_amount_threshold`: 50000.0<br>• `bonus_count_points`: 15<br>• `bonus_count_threshold`: 10<br>• `min_count`: 6<br>• `window_minutes`: 60 |
| `R02` | **NEW_DEVICE_ACTIVITY** | DETECTION | 55 | Significant debit activity on a newly observed device for an established account | • `bonus_emulator_or_shared_accounts`: 3<br>• `bonus_emulator_points`: 15<br>• `bonus_large_amount`: 50000.0<br>• `bonus_large_points`: 15<br>• `min_amount`: 15000.0<br>• `min_prior_account_txns`: 5 |
| `R03` | **CIRCULAR_TRANSFER** | DETECTION | 60 | Circular transfer path where funds return to origin account within 72 hours | • `bonus_distinct_customers`: 3<br>• `bonus_distinct_customers_points`: 20<br>• `bonus_retention_points`: 15<br>• `bonus_retention_ratio`: 0.9<br>• `max_hops`: 5<br>• `max_window_hours`: 72<br>• `min_hops`: 2<br>• `min_transfer_amount`: 5000.0 |
| `R04` | **DORMANT_REACTIVATION** | DETECTION | 55 | Substantial transaction following a period of inactivity exceeding 180 days | • `bonus_debit_drain_points`: 25<br>• `bonus_debit_drain_ratio`: 0.8<br>• `bonus_new_device_points`: 15<br>• `inactivity_gap_days`: 180<br>• `min_amount`: 10000.0 |
| `R05` | **AMOUNT_OUTLIER** | DETECTION | 45 | Debit transaction significantly exceeding historical baseline median | • `bonus_extreme_multiplier`: 15.0<br>• `bonus_extreme_points`: 15<br>• `bonus_high_risk_merchant_points`: 10<br>• `min_amount`: 25000.0<br>• `min_prior_debits`: 5<br>• `outlier_multiplier`: 8.0 |
