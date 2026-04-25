#!/usr/bin/env python3
"""端到端 demo runner — 跑完整 pipeline 给一个患者出报告"""

import sys
import subprocess
import time
import os
from pathlib import Path

DEMO_DIR = Path("/Users/wenshaoyue/Desktop/research/AD MIND/demo")
DATA_DIR = Path("/Users/wenshaoyue/Desktop/research/AD MIND/data_v2")


def run_step(name, script, patient_id):
    print(f"\n{'='*60}\n[{name}] 跑 {script}\n{'='*60}")
    script_path = DEMO_DIR / script
    if not script_path.exists():
        print(f"✗ 脚本不存在: {script_path}")
        return False
    t0 = time.time()
    result = subprocess.run(
        ["python3", str(script_path), patient_id],
        capture_output=True, text=True
    )
    elapsed = time.time() - t0
    if result.returncode != 0:
        print(f"✗ 失败 ({elapsed:.1f}s)")
        if result.stdout:
            print("--- stdout (尾部 2000 字符) ---")
            print(result.stdout[-2000:])
        if result.stderr:
            print("--- stderr (尾部 2000 字符) ---")
            print(result.stderr[-2000:])
        return False
    if result.stdout:
        print(result.stdout[-1500:])  # 末尾 1500 字符
    print(f"✓ 完成 ({elapsed:.1f}s)")
    return True


def print_final_report(pdir):
    """漂亮的 final report — 列出输出文件 + 预览 dashboard/report"""
    print(f"\n{'#'*60}")
    print(f"# Pipeline 完成! 输出文件:")
    print(f"{'#'*60}")
    files = [
        "facts.json",
        "insights_physio.json",
        "insights_behavior.json",
        "insights_clinical.json",
        "dashboard.json",
        "report.md",
    ]
    for f in files:
        path = pdir / f
        if path.exists():
            size_kb = path.stat().st_size / 1024
            print(f"  ✓ {path.name:<28} ({size_kb:>6.1f} KB)")
        else:
            print(f"  ✗ {path.name:<28} (缺失)")

    # 如果 report.md 存在，预览前 60 行
    report_path = pdir / "report.md"
    if report_path.exists():
        print(f"\n{'-'*60}")
        print(f"  Report 预览 ({report_path}):")
        print(f"{'-'*60}")
        try:
            with open(report_path, "r", encoding="utf-8") as fh:
                lines = fh.readlines()
            for line in lines[:60]:
                print(f"  {line.rstrip()}")
            if len(lines) > 60:
                print(f"  ... (剩余 {len(lines) - 60} 行省略)")
        except Exception as e:
            print(f"  读取失败: {e}")

    print(f"\n{'#'*60}")
    print(f"# 看完整输出:")
    print(f"{'#'*60}")
    print(f"  cat {pdir}/report.md")
    print(f"  cat {pdir}/dashboard.json")


def main():
    patient_id = sys.argv[1] if len(sys.argv) > 1 else "P02"

    # 检查 API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠ 警告: 未设置 ANTHROPIC_API_KEY")
        print("Analyzer 仍能跑 (无 LLM), 但 3 个 Agent + Narrator 会失败")
        print("export ANTHROPIC_API_KEY='sk-ant-...' 后重试")
        print()

    pdir = DATA_DIR / patient_id
    if not pdir.exists():
        print(f"✗ 患者目录不存在: {pdir}")
        print("先跑 01_generator_v2.py 生成数据")
        sys.exit(1)

    print(f"\n{'#'*60}")
    print(f"# AD Multi-Agent Pipeline Demo")
    print(f"# Patient: {patient_id}")
    print(f"# Pipeline: Analyzer → 3 Agent → Narrator")
    print(f"{'#'*60}")

    pipeline = [
        ("Analyzer (rule-based, 统计)", "02_analyzer.py"),
        ("PhysioAgent (LLM)", "03_physio_agent.py"),
        ("BehaviorAgent (LLM)", "04_behavior_agent.py"),
        ("ClinicalAgent (LLM)", "05_clinical_agent.py"),
        ("Narrator (LLM)", "06_narrator.py"),
    ]

    overall_t0 = time.time()
    for name, script in pipeline:
        ok = run_step(name, script, patient_id)
        if not ok:
            print(f"\n⚠ {name} 失败, pipeline 中断")
            sys.exit(1)
    overall_elapsed = time.time() - overall_t0

    print_final_report(pdir)
    print(f"\n总耗时: {overall_elapsed:.1f}s")


if __name__ == "__main__":
    main()
