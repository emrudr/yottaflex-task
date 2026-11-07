# Assumptions and Limitations

This document records the architectural assumptions, implementation choices, deliberate simplifications, and operational limitations governing the synthetic data generation and risk prioritization pipeline.

---

## 1. Architectural Assumptions

1. **Account Identifier Format Choice:**
   - Account primary keys follow the literal format `ACC-CUS-NNNNNN-NN` (e.g. `ACC-CUS-000001-01`). This format couples the owning customer identifier directly to the account while guaranteeing deterministic unique numbering.

2. **Currency Standardization:**
   - All monetary balances and transactions are denominated strictly in Indian Rupees (`INR`), formatted to 2 decimal places. Cross-currency exchange rate fluctuations are not simulated.

3. **Batch Rule Evaluation:**
   - Rules are evaluated in batch mode across the complete historical transaction window rather than on an asynchronous real-time event streaming bus.

4. **Deterministic Rule-Based Triage (No ML):**
   - Analyst triage and dispositions are modeled via explainable business thresholds based on observable risk scores (scores $\ge 70 \to \text{TRUE\_POSITIVE}$, $< 50 \to \text{FALSE\_POSITIVE}$, $50..69 \to \text{ESCALATE}$).

5. **Strict Ground-Truth Isolation:**
   - Ground truth records are written exclusively to `output/ground_truth/` and are guarded by an environment variable check (`ALLOW_GT=1`) to prevent data leakage into detection logic.

6. **Injected Overdraft Anomalies and R05 Rule Interaction:**
   - Injected negative balance anomalies (`INJ_NEGATIVE_BALANCE_NO_OD`) utilize a substantial debit (~₹35,000) to deliberately breach the zero-overdraft threshold. Because ₹35,000 exceeds ₹25,000 and 8× historical account median, these debits legitimately trigger rule `R05` (`AMOUNT_OUTLIER`), creating 10 baseline R05 alerts in addition to the data quality anomaly label.

7. **Routine Background Transfers and Acyclic Topography:**
   - Approximately 3% of the background budget is allocated to routine domestic transfer pairs (`NEFT_TRANSFER_OUT` debit + `TRANSFER_IN` credit) linking random active accounts. To mathematically guarantee that routine transfers can never inadvertently form circular wash rings, the generator enforces a strict topological ordering where the source account identifier always sorts lexicographically lower than the destination identifier (`source_account_id < dest_account_id`). This creates a Directed Acyclic Graph (DAG), rendering cycle formation structurally impossible and ensuring rule `R03` (`CIRCULAR_TRANSFER`) fires only on deliberately planted rings.

---

## 2. What Was Deliberately Left Out

To maintain strict conceptual simplicity and interview explainability, the following non-essential components were deliberately omitted or removed:

1. **Count-Calibration Loops & Top-Up Events:**
   - Removed iterative post-hoc count correction and safety-net credits. Exact transaction count ($N_{target}$) is achieved by construction through budget subtraction ($N_{bg} = N_{target} - N_{scn} - N_{inj}$) and largest remainder integer allocation.

2. **Primary-Rule Merging & Corroboration Heuristics:**
   - Removed complex multi-rule merging, corroboration matrices, and arbitrary alert capping. Every rule match produces exactly one alert; alerts occurring on the same account within 7 days are naturally unified into a single case via union-find clustering.

3. **Complex Merchant Historical Profiling:**
   - Removed stateful merchant payee categorization (`A01` recurring payee logic) and device retirement tracking. Adjustments were reduced to two transparent modifiers: `A01` (same-owner transfer) and `A02` (trusted customer tenure/KYC).

4. **Multi-Role Reassignment Chains:**
   - Removed complex `REASSIGN` workflows. System administrative routing (`ANL-012`) assigns cases directly to operations analysts (`ANL-001`..`008`), with clear single-hop escalation to risk reviewers (`ANL-009`..`011`) for borderline scores.

5. **Customer Count CLI Overrides:**
   - Presets (`starter` and `full`) strictly govern dataset scaling to ensure reproducible, predictable volume targets without ad-hoc parameter collisions.

---

## 3. Pipeline Limitations

1. **In-Memory Scale:**
   - Data processing assumes collections fit in standard memory. Starter scale (5,000 txns) executes in $\approx 2$ seconds, while full scale (100,000 txns) completes in $\approx 20$ seconds.

2. **Single-Institution Domestic Transfers:**
   - Bilateral fund transfers occur strictly between internal accounts within the synthetic institution using paired `NEFT_TRANSFER_OUT` and `TRANSFER_IN` legs. Cross-border banking rails (SWIFT) are not modeled.
