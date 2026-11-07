"""Reproducibility test harness: Runs pipeline twice and validates identical SHA-256 checksums."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Tuple

from config import SEED
from io_utils import compute_sha256, ensure_dir

def count_lines(path: Path) -> int:
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return sum(1 for _ in f)

def compare_runs(dir_a: Path, dir_b: Path, reports_dir: Path) -> bool:
    print(f"\n[*] Comparing outputs between:\n    Run A: {dir_a}\n    Run B: {dir_b}")

    subdirs = ["data", "ground_truth", "sql", "reports"]
    all_matched = True

    comparison_results: List[Dict[str, Any]] = []

    for sdir in subdirs:
        sub_a = dir_a / sdir
        sub_b = dir_b / sdir

        files_a = {p.relative_to(sub_a): p for p in sub_a.rglob("*") if p.is_file()}
        files_b = {p.relative_to(sub_b): p for p in sub_b.rglob("*") if p.is_file()}

        all_rel_files = sorted(set(files_a.keys()) | set(files_b.keys()))

        for rel_f in all_rel_files:
            rel_path_str = f"{sdir}/{rel_f}"
            p_a = files_a.get(rel_f)
            p_b = files_b.get(rel_f)

            if not p_a or not p_b:
                comparison_results.append({
                    "file": rel_path_str,
                    "status": "MISSING_FILE",
                    "rows_a": count_lines(p_a) if p_a else 0,
                    "rows_b": count_lines(p_b) if p_b else 0,
                    "sha256_match": False,
                })
                all_matched = False
                continue

            sha_a = compute_sha256(p_a)
            sha_b = compute_sha256(p_b)
            rows_a = count_lines(p_a)
            rows_b = count_lines(p_b)

            is_match = (sha_a == sha_b) and (rows_a == rows_b)
            if not is_match:
                all_matched = False

            comparison_results.append({
                "file": rel_path_str,
                "status": "MATCH" if is_match else "MISMATCH",
                "rows_a": rows_a,
                "rows_b": rows_b,
                "sha256_a": sha_a[:12] + "...",
                "sha256_b": sha_b[:12] + "...",
                "sha256_match": is_match,
            })

    # Print summary table
    print("\n-------------------------------------------------------------------------------------")
    print(f"{'Relative File Path':<35} | {'Run A Rows':>10} | {'Run B Rows':>10} | {'Status':>8}")
    print("-------------------------------------------------------------------------------------")
    for r in comparison_results:
        print(f"{r['file']:<35} | {r['rows_a']:>10} | {r['rows_b']:>10} | {r['status']:>8}")
    print("-------------------------------------------------------------------------------------\n")

    overall_status = "PASS" if all_matched else "FAIL"
    print(f"[*] Overall Reproducibility Status: {overall_status}\n")

    # Write output/reports/reproducibility.md
    md_lines = [
        "# Pipeline Determinism & Reproducibility Audit",
        "",
        f"**Audit Status:** `{overall_status}`",
        "",
        "This report compares identical consecutive pipeline executions across independent runs using fixed random seeds without timestamps or wall-clock dependencies.",
        "",
        "| File Path | Run A Rows | Run B Rows | Checksum Status |",
        "|---|---|---|---|",
    ]
    for r in comparison_results:
        md_lines.append(f"| `{r['file']}` | {r['rows_a']} | {r['rows_b']} | `{'IDENTICAL' if r['sha256_match'] else 'MISMATCH'}` |")
    md_lines.append("")

    repro_md_path = reports_dir / "reproducibility.md"
    ensure_dir(reports_dir)
    with open(repro_md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines))

    print(f"[+] Written audit report to {repro_md_path}")
    return all_matched

def main():
    parser = argparse.ArgumentParser(description="Check pipeline reproducibility between consecutive runs")
    parser.add_argument("--seed", type=int, default=SEED, help="Random seed")
    parser.add_argument("--scale", type=str, default="starter", choices=["starter", "full"], help="Scale preset")
    parser.add_argument("--out", type=str, default="output", help="Base output directory")
    args = parser.parse_args()

    base_dir = Path(args.out)
    repro_dir = base_dir / "_repro"
    dir_a = repro_dir / "run_a"
    dir_b = repro_dir / "run_b"

    py = sys.executable

    print(f"[*] Running Pipeline Execution A (Target: {dir_a})...")
    res_a = subprocess.run([py, "run_all.py", "--seed", str(args.seed), "--scale", args.scale, "--out", str(dir_a)])
    if res_a.returncode != 0:
        print("[!] Execution A failed!")
        sys.exit(res_a.returncode)

    print(f"\n[*] Running Pipeline Execution B (Target: {dir_b})...")
    res_b = subprocess.run([py, "run_all.py", "--seed", str(args.seed), "--scale", args.scale, "--out", str(dir_b)])
    if res_b.returncode != 0:
        print("[!] Execution B failed!")
        sys.exit(res_b.returncode)

    reports_dir = base_dir / "reports"
    passed = compare_runs(dir_a, dir_b, reports_dir)
    if not passed:
        sys.exit(1)

if __name__ == "__main__":
    main()

