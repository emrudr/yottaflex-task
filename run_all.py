"""Orchestrator: Executes the entire risk prioritization pipeline end-to-end."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from config import SEED

def run_step(cmd: List[str], desc: str):
    print(f"\n==================================================")
    print(f"[*] Step: {desc}")
    print(f"[*] Command: {' '.join(cmd)}")
    print(f"==================================================")
    res = subprocess.run(cmd)
    if res.returncode != 0:
        print(f"\n[!] Pipeline step failed: {desc} (Exit code: {res.returncode})")
        sys.exit(res.returncode)

def main():
    parser = argparse.ArgumentParser(description="Run complete synthetic pipeline end-to-end")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed for generation")
    parser.add_argument("--scale", type=str, default="starter", choices=["starter", "full"], help="Scale preset")
    parser.add_argument("--customers", type=int, default=None, help="Optional customer count override")
    parser.add_argument("--out", type=str, default="output", help="Output directory")
    args = parser.parse_args()

    py = sys.executable

    # 1. Stage 1: Generate
    gen_cmd = [py, "generate.py", "--seed", str(args.seed), "--scale", args.scale, "--out", args.out]
    if args.customers:
        gen_cmd.extend(["--customers", str(args.customers)])
    run_step(gen_cmd, "Stage 1: Generate Synthetic Data")

    # 2. Stage 2: Run Rules
    rules_cmd = [py, "run_rules.py", "--out", args.out]
    run_step(rules_cmd, "Stage 2: Evaluate Risk Rules & Triage Cases")

    # 3. Stage 2b: Inject Alert Anomalies
    inj_cmd = [py, "inject_alert_anomalies.py", "--seed", str(args.seed), "--out", args.out]
    run_step(inj_cmd, "Stage 2b: Inject Labelled Alert-Level Anomalies")

    # 4. Export SQL & Verify SQLite
    sql_cmd = [py, "export_sql.py", "--out", args.out, "--verify"]
    run_step(sql_cmd, "Database Export: Generate & Verify seed.sql")

    # 5. Stage 3: Validate
    val_cmd = [py, "validate.py", "--out", args.out]
    run_step(val_cmd, "Stage 3: Validate Structural Integrity & Recall")

    print("\n==================================================")
    print("[+] FULL PIPELINE EXECUTION COMPLETED SUCCESSFULLY")
    print("==================================================\n")

if __name__ == "__main__":
    main()

