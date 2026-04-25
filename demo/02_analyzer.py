"""Analyzer — Rule-based fact extraction
对一个患者的 30 天数据跑统计, 输出 DataFact 清单
不调 LLM, 纯 Python 算式
"""

import sys, json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Literal
import numpy as np
import pandas as pd
from scipy.stats import linregress

ROOT = Path("/Users/wenshaoyue/Desktop/research")
DATA_V2 = ROOT / "AD MIND" / "data_v2"
BASELINE_REF = ROOT / "AD" / "data" / "baseline 4.8" / "normal_reference_ranges.csv"

# ── DataFact ──
@dataclass
class DataFact:
    fact_type: Literal["outlier", "trend", "comparison", "difference", "extreme"]
    entity: str
    modality: str
    template_text: str
    severity: float  # 0-1
    evidence: dict


# ── Analyzer 主体 ──
class Analyzer:
    def __init__(self, baseline_csv: Path):
        self.baseline = pd.read_csv(baseline_csv).set_index("task")

    def discover(self, patient_dir: Path) -> list[DataFact]:
        facts = []
        # 1. Sensor outlier + trend (按特征跨日聚合)
        facts.extend(self._analyze_sensors(patient_dir))
        # 2. EMA 趋势
        facts.extend(self._analyze_ema(patient_dir))
        # 3. 量表变化
        facts.extend(self._analyze_surveys(patient_dir))
        # 4. 双任务代价
        facts.extend(self._dtc(patient_dir))
        return facts

    def _analyze_sensors(self, patient_dir: Path) -> list[DataFact]:
        """对每个特征: 算每天均值/std → outlier (z-score) + trend (linregress)"""
        facts = []
        sensor_dir = patient_dir / "sensor"
        if not sensor_dir.exists():
            return facts

        # 收集每天每任务的特征
        # 特征列表: (column, summary_func, baseline_field)
        FEATURES = [
            ("svm",          "std",  "svm_std_mean",   "svm_std_sd",   "imu",  "SVM 变异 (步态稳定性)"),
            ("svm",          "mean", "svm_mean_mean",  "svm_mean_sd",  "imu",  "SVM 均值 (运动强度)"),
            ("jerk",         "std",  "jerk_std_mean",  "jerk_std_sd",  "imu",  "Jerk 变异 (步态平稳性)"),
            ("hr_bpm_avg",   "std",  "hr_std_mean",    "hr_std_sd",    "ppg",  "HR 变异 (HRV)"),
            ("hr_bpm_avg",   "mean", "hr_mean_mean",   "hr_mean_sd",   "ppg",  "HR 均值"),
            ("gsr_filtered", "mean", "gsr_mean_mean",  "gsr_mean_sd",  "eda",  "EDA 基线"),
            ("gsr_filtered", "std",  "gsr_std_mean",   "gsr_std_sd",   "eda",  "EDA 变异"),
        ]

        # 按任务收集每日序列
        for task in ["walking_normal", "walking_dual_task", "balance_standing", "hand_fine_motor"]:
            if task not in self.baseline.index:
                continue
            base_row = self.baseline.loc[task]

            for col, agg, base_field, base_sd_field, modality, label in FEATURES:
                if base_field not in base_row.index:
                    continue
                base_mean = base_row[base_field]
                base_sd = base_row[base_sd_field]
                if pd.isna(base_mean) or pd.isna(base_sd) or base_sd == 0:
                    continue

                # 收集 30 天该特征值
                series = []
                for f in sorted(sensor_dir.glob(f"day*_{task}.csv")):
                    day = int(f.stem.split("_")[0].replace("day", ""))
                    df = pd.read_csv(f)
                    if col not in df.columns:
                        continue
                    valid = df[col].dropna()
                    if col == "hr_bpm_avg":
                        valid = valid[valid > 0]
                    if len(valid) < 5:
                        continue
                    val = valid.std() if agg == "std" else valid.mean()
                    series.append((day, float(val)))

                if len(series) < 5:
                    continue

                # ─ Outlier: 最近 3 天均值 vs baseline ─
                recent = np.mean([v for _, v in series[-3:]])
                z = (recent - base_mean) / base_sd
                if abs(z) > 2.0:
                    facts.append(DataFact(
                        fact_type="outlier",
                        entity=f"{label}@{task}",
                        modality=modality,
                        template_text=f"[{task}] {label} 异常{'升高' if z>0 else '下降'}至 {recent:.2f} (基线 {base_mean:.2f}±{base_sd:.2f}, z={z:+.1f})",
                        severity=min(abs(z) / 3, 1.0),
                        evidence={"current": recent, "baseline_mean": base_mean, "baseline_sd": base_sd, "z_score": z},
                    ))

                # ─ Trend: 30 天回归 ─
                days, vals = zip(*series)
                if len(days) >= 7:
                    slope, intercept, r, p_val, _ = linregress(days, vals)
                    if p_val < 0.05 and abs(r) > 0.4:
                        direction = "上升" if slope > 0 else "下降"
                        facts.append(DataFact(
                            fact_type="trend",
                            entity=f"{label}@{task}",
                            modality=modality,
                            template_text=f"[{task}] {label} 在过去 {len(days)} 天呈 {direction} 趋势 ({vals[0]:.2f} → {vals[-1]:.2f}, r={r:.2f}, p={p_val:.3f})",
                            severity=min(abs(r), 1.0),
                            evidence={"slope_per_day": slope, "r": r, "p": p_val, "n_days": len(days)},
                        ))
        return facts

    def _analyze_ema(self, patient_dir: Path) -> list[DataFact]:
        ema_file = patient_dir / "ema.jsonl"
        if not ema_file.exists():
            return []
        records = [json.loads(l) for l in ema_file.read_text().strip().split("\n")]
        if len(records) < 10:
            return []
        df = pd.DataFrame(records)

        facts = []
        for col, label in [("mood", "EMA 情绪"), ("sleep_quality", "EMA 睡眠质量"),
                           ("anxiety", "EMA 焦虑"), ("energy", "EMA 精力")]:
            if col not in df.columns:
                continue
            daily = df.groupby("day")[col].mean()
            if len(daily) < 7:
                continue
            slope, _, r, p_val, _ = linregress(daily.index, daily.values)
            if p_val < 0.05 and abs(r) > 0.3:
                direction = "下降" if slope < 0 else "上升"
                facts.append(DataFact(
                    fact_type="trend",
                    entity=col,
                    modality="ema",
                    template_text=f"{label} 在过去 {len(daily)} 天呈 {direction} 趋势 (起点 {daily.iloc[0]:.1f}/10 → 末点 {daily.iloc[-1]:.1f}/10, r={r:.2f})",
                    severity=min(abs(r), 1.0),
                    evidence={"slope": slope, "r": r, "p": p_val},
                ))
        return facts

    def _analyze_surveys(self, patient_dir: Path) -> list[DataFact]:
        sf = patient_dir / "surveys.jsonl"
        if not sf.exists():
            return []
        records = [json.loads(l) for l in sf.read_text().strip().split("\n")]
        if len(records) < 2:
            return []
        df = pd.DataFrame(records)

        facts = []
        for col, label, threshold in [
            ("mmse_estimate", "MMSE", 1.5),
            ("moca_estimate", "MoCA", 1.5),
            ("phq9", "PHQ-9 抑郁分", 3),
        ]:
            if col not in df.columns:
                continue
            v0, v_last = df[col].iloc[0], df[col].iloc[-1]
            delta = v_last - v0
            if abs(delta) >= threshold:
                facts.append(DataFact(
                    fact_type="comparison",
                    entity=col,
                    modality="survey",
                    template_text=f"{label} 由 {v0:.1f} 变化至 {v_last:.1f} (Δ={delta:+.1f})",
                    severity=min(abs(delta) / 10, 1.0),
                    evidence={"initial": v0, "final": v_last, "delta": delta},
                ))
        return facts

    def _dtc(self, patient_dir: Path) -> list[DataFact]:
        """双任务代价"""
        sensor_dir = patient_dir / "sensor"
        if not sensor_dir.exists():
            return []

        # 取最后 5 天的 single 和 dual
        single_speeds = []
        dual_speeds = []
        for day in range(25, 30):
            sf = sensor_dir / f"day{day:02d}_walking_normal.csv"
            df_file = sensor_dir / f"day{day:02d}_walking_dual_task.csv"
            if sf.exists() and df_file.exists():
                s_df = pd.read_csv(sf)
                d_df = pd.read_csv(df_file)
                if "svm" in s_df.columns and "svm" in d_df.columns:
                    single_speeds.append(s_df["svm"].mean())
                    dual_speeds.append(d_df["svm"].mean())

        if len(single_speeds) < 3:
            return []
        s = np.mean(single_speeds)
        d = np.mean(dual_speeds)
        if s == 0:
            return []
        dtc_pct = (s - d) / s * 100
        if abs(dtc_pct) > 15:
            return [DataFact(
                fact_type="difference",
                entity="dual_task_cost",
                modality="imu",
                template_text=f"双任务代价 {dtc_pct:+.1f}% (单任务 SVM {s:.2f}, 双任务 SVM {d:.2f}, 最近 5 天)",
                severity=min(abs(dtc_pct) / 50, 1.0),
                evidence={"single": s, "dual": d, "dtc_pct": dtc_pct},
            )]
        return []


# ── 主入口 ──
def main(patient_id="P01"):
    patient_dir = DATA_V2 / patient_id
    if not patient_dir.exists():
        print(f"✗ {patient_dir} 不存在")
        return None

    analyzer = Analyzer(BASELINE_REF)
    facts = analyzer.discover(patient_dir)

    print(f"=== Analyzer 输出 — {patient_id} ===")
    print(f"共 {len(facts)} 条 DataFact:\n")
    for i, f in enumerate(facts, 1):
        print(f"{i:2d}. [{f.fact_type:11s}] {f.template_text}")
        print(f"     severity={f.severity:.2f}, modality={f.modality}")
        print()

    # 写出
    out_file = patient_dir / "facts.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump([asdict(x) for x in facts], f, ensure_ascii=False, indent=2)
    print(f"✓ 写入: {out_file}")
    return facts


if __name__ == "__main__":
    pid = sys.argv[1] if len(sys.argv) > 1 else "P02"  # P02 stepwise 进展明显, 容易出 fact
    main(pid)
