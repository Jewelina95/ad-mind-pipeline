#!/usr/bin/env python3
"""Pipeline 状态检查 — 看看每个 patient 跑到哪一步了"""

import sys
from pathlib import Path

DATA_DIR = Path("/Users/wenshaoyue/Desktop/research/AD MIND/data_v2")
DEMO_DIR = Path("/Users/wenshaoyue/Desktop/research/AD MIND/demo")

# 步骤 → 产物文件 (按 pipeline 顺序)
STEPS = [
    ("Generator",     "raw 数据 (events_*.jsonl 等)"),  # 特殊处理
    ("Analyzer",      "facts.json"),
    ("PhysioAgent",   "insights_physio.json"),
    ("BehaviorAgent", "insights_behavior.json"),
    ("ClinicalAgent", "insights_clinical.json"),
    ("Narrator",      "dashboard.json + report.md"),
]


def check_generator(pdir):
    """Generator 产物 — events_*.jsonl 或类似 raw 数据"""
    raw_files = list(pdir.glob("events_*.jsonl")) + list(pdir.glob("*.jsonl"))
    raw_files += list(pdir.glob("raw_*.json"))
    return len(raw_files) > 0


def check_step(pdir, artifact):
    """检查产物文件是否存在 — 支持 'a + b' 形式"""
    if "+" in artifact:
        parts = [p.strip() for p in artifact.split("+")]
        return all((pdir / p).exists() for p in parts)
    # 把描述字符串里只取第一个 .json/.md 文件名
    fname = artifact.split()[0]
    return (pdir / fname).exists()


def step_status(pdir, idx, artifact):
    if idx == 0:
        return check_generator(pdir)
    return check_step(pdir, artifact)


def file_size_str(pdir, fname):
    path = pdir / fname
    if not path.exists():
        return ""
    size = path.stat().st_size
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / 1024 / 1024:.1f} MB"


def suggest_next(done_steps, total_steps):
    """根据已完成步骤推荐下一步"""
    if done_steps == 0:
        return "跑 01_generator_v2.py 生成数据"
    if done_steps == total_steps:
        return "全部完成! 看 report.md / dashboard.json"
    next_idx = done_steps  # 0-indexed
    script_map = {
        1: "02_analyzer.py",
        2: "03_physio_agent.py",
        3: "04_behavior_agent.py",
        4: "05_clinical_agent.py",
        5: "06_narrator.py",
    }
    script = script_map.get(next_idx, "?")
    return f"跑 {script} (或 07_run_all.py 一键跑完)"


def patient_summary(pdir):
    """单个 patient 的状态"""
    pid = pdir.name
    statuses = []
    done_count = 0
    for idx, (name, artifact) in enumerate(STEPS):
        ok = step_status(pdir, idx, artifact)
        statuses.append((name, artifact, ok))
        if ok:
            done_count += 1

    print(f"\n  Patient {pid}  [{done_count}/{len(STEPS)} 步]")
    for name, artifact, ok in statuses:
        mark = "✓" if ok else "✗"
        # 显示文件大小
        size_info = ""
        if ok and "+" not in artifact and artifact != "raw 数据 (events_*.jsonl 等)":
            fname = artifact.split()[0]
            size_info = f"  ({file_size_str(pdir, fname)})"
        elif ok and "+" in artifact:
            parts = [p.strip() for p in artifact.split("+")]
            sizes = [file_size_str(pdir, p) for p in parts]
            size_info = "  (" + ", ".join(f"{p}: {s}" for p, s in zip(parts, sizes)) + ")"
        print(f"    {mark} {name:<14} → {artifact}{size_info}")
    print(f"    >>> 下一步: {suggest_next(done_count, len(STEPS))}")
    return done_count, len(STEPS)


def main():
    print(f"{'#'*60}")
    print(f"# AD MIND Pipeline 状态检查")
    print(f"# Data dir: {DATA_DIR}")
    print(f"{'#'*60}")

    if not DATA_DIR.exists():
        print(f"\n✗ data 目录不存在: {DATA_DIR}")
        print("  先跑 01_generator_v2.py 生成数据")
        sys.exit(1)

    # 找所有 patient 目录 (P01, P02, ...)
    patient_dirs = sorted(
        [p for p in DATA_DIR.iterdir() if p.is_dir() and p.name.startswith("P")]
    )

    if not patient_dirs:
        print(f"\n✗ 未发现任何 patient 目录 (期望 P01/P02/...)")
        print("  先跑 01_generator_v2.py 生成数据")
        sys.exit(1)

    print(f"\n发现 {len(patient_dirs)} 个 patient:")
    for p in patient_dirs:
        print(f"  - {p.name}")

    # 单 patient 详细状态
    total_done = 0
    total_steps = 0
    for pdir in patient_dirs:
        done, steps = patient_summary(pdir)
        total_done += done
        total_steps += steps

    # 全局 summary
    print(f"\n{'#'*60}")
    print(f"# 全局总结")
    print(f"{'#'*60}")
    print(f"  Patient 数: {len(patient_dirs)}")
    print(f"  完成步骤总数: {total_done}/{total_steps}")
    completion = (total_done / total_steps * 100) if total_steps else 0
    print(f"  完成度: {completion:.1f}%")

    # 推荐动作
    fully_done = [p for p in patient_dirs
                  if all(step_status(p, i, a) for i, (_, a) in enumerate(STEPS))]
    fully_pending = [p for p in patient_dirs
                     if not check_generator(p)]
    in_progress = [p for p in patient_dirs
                   if p not in fully_done and p not in fully_pending]

    print(f"\n  全部完成: {len(fully_done)} ({[p.name for p in fully_done] or '无'})")
    print(f"  进行中:   {len(in_progress)} ({[p.name for p in in_progress] or '无'})")
    print(f"  未开始:   {len(fully_pending)} ({[p.name for p in fully_pending] or '无'})")

    print(f"\n{'#'*60}")
    print(f"# 建议下一步")
    print(f"{'#'*60}")
    if fully_pending:
        print(f"  python3 {DEMO_DIR}/01_generator_v2.py    # 生成 raw 数据")
    if in_progress:
        # 选第一个进行中的 patient 给出建议
        p = in_progress[0]
        done = sum(1 for i, (_, a) in enumerate(STEPS) if step_status(p, i, a))
        print(f"  python3 {DEMO_DIR}/07_run_all.py {p.name}    # 一键跑完 {p.name}")
    if not in_progress and not fully_pending and fully_done:
        p = fully_done[0]
        print(f"  cat '{DATA_DIR / p.name / 'report.md'}'    # 看报告")


if __name__ == "__main__":
    main()
