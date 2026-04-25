"""Narrator — 把 PhysioAgent + BehaviorAgent + ClinicalAgent 的 Insight
整合为 MIND 风格的 Narrative Dashboard.

输入:
  - insights_physio.json    (PhysioAgent 输出)
  - insights_behavior.json  (BehaviorAgent 输出)
  - insights_clinical.json  (ClinicalAgent 输出)
  - persona.json
  - progression.csv         图表数据
  - surveys.jsonl           图表数据
  - ema.jsonl               图表数据
  - notes.jsonl             session_recap

输出:
  - dashboard.json          (机器可读 dashboard)
  - report.md               (人类可读 markdown 报告)

设计来自 系统完整设计_v2.md 第 7 节 NARRATOR LAYER.

LLM 调用:
  1. insight 渲染成两段式 markdown card (批量, top 5)
  2. summary_today (≤12 字)
失败时降级为模板渲染.
"""

import sys, json, os, csv
from pathlib import Path
from collections import defaultdict

ROOT = Path("/Users/wenshaoyue/Desktop/research")
DATA_V2 = ROOT / "AD MIND" / "data_v2"

NARRATOR_SYSTEM_PROMPT = """你是 MIND 系统的临床叙事编辑 (Narrator). 你的任务是把多条临床 Insight 渲染成医生可读的 markdown 卡片.

## 渲染规则
每条 Insight 输出严格的两段式 markdown:

```
## {标题, 中文, ≤15 字, 概括核心现象}

{客观观察一段, 用陈述句, 复述 observation 字段, 30-60 字}

**{临床含义, 用 markdown 加粗, 复述 clinical_implication 字段, 30-60 字}**
```

## 注意
- 标题精炼, 不带标点
- 第一段是客观事实, 不下结论
- 第二段加粗包裹整段, 是临床解读
- 不要添加额外推理, 只渲染现有信息
- 多条 Insight 之间用 `---` 分隔

## 输出
直接输出 markdown 文本, 不要 ```markdown``` 代码块, 不要其他解释."""

SUMMARY_SYSTEM_PROMPT = """你是 MIND 临床简报员. 任务: 把若干条 Insight 浓缩为 ≤12 字的中文一句话总结, 用于 Dashboard 顶部.

## 规则
- 严格 ≤12 个汉字 (标点不算)
- 抓核心异常, 给行动建议
- 例: "步态恶化, 建议复诊筛查" / "情绪波动, 注意 BPSD"
- 直接输出, 不要解释, 不要引号"""


# -------- Step 1: Threader (无 LLM) --------

def thread_insights(physio: list, behavior: list, clinical: list) -> dict:
    """按 alert_level + confidence 排序, 拆 primary / secondary."""
    all_insights = []
    for ins in physio:
        ins.setdefault("agent", "physio")
        all_insights.append(ins)
    for ins in behavior:
        ins.setdefault("agent", "behavior")
        all_insights.append(ins)
    for ins in clinical:
        ins.setdefault("agent", "clinical")
        all_insights.append(ins)

    primary = [
        i for i in all_insights
        if i.get("alert_level") == "red" or i.get("confidence", 0) > 0.8
    ]
    secondary = [i for i in all_insights if i not in primary]
    primary.sort(key=lambda x: -x.get("confidence", 0))
    secondary.sort(key=lambda x: -x.get("confidence", 0))
    return {"primary": primary, "secondary": secondary, "all": all_insights}


# -------- Step 2: Insight Narration (LLM 抛光) --------

def render_cards_template(insights: list) -> list:
    """无 LLM 模板渲染降级."""
    cards = []
    for ins in insights:
        obs = ins.get("observation", "").strip()
        ci = ins.get("clinical_implication", "").strip()
        # 标题: 取 observation 前 12 字
        title = obs.split("(")[0].split(",")[0].split("，")[0][:12] or "临床观察"
        card = f"## {title}\n\n{obs}\n\n**{ci}**" if ci else f"## {title}\n\n{obs}"
        cards.append(card)
    return cards


def render_cards_llm(insights: list) -> list:
    """批量调 Claude 把 top insight 渲染成两段式."""
    if not insights:
        return []
    try:
        import anthropic
    except ImportError:
        print("⚠ anthropic 未安装, 降级为模板渲染")
        return render_cards_template(insights)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("⚠ 没有 ANTHROPIC_API_KEY, 降级为模板渲染")
        return render_cards_template(insights)

    user_lines = ["## 待渲染的 Insight 清单 (按重要性排序)\n"]
    for i, ins in enumerate(insights, 1):
        user_lines.append(f"### Insight {i} (id={ins.get('id', '?')}, agent={ins.get('agent', '?')})")
        user_lines.append(f"- observation: {ins.get('observation', '')}")
        user_lines.append(f"- clinical_implication: {ins.get('clinical_implication', '')}")
        if ins.get("differential"):
            user_lines.append(f"- differential: {ins['differential']}")
        user_lines.append(f"- confidence: {ins.get('confidence', 0):.2f}")
        user_lines.append("")
    user_lines.append("## 任务")
    user_lines.append("把以上每条 Insight 渲染成两段式 markdown card. 多条之间用 `---` 分隔. 严格按系统提示的格式.")

    user_prompt = "\n".join(user_lines)

    try:
        client = anthropic.Anthropic()
        print(f"→ Narrator 调 Claude 渲染 {len(insights)} 条 card")
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            temperature=0.3,
            system=[{
                "type": "text",
                "text": NARRATOR_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
        )
        raw = response.content[0].text.strip()
        print(f"→ {response.usage.input_tokens} input + {response.usage.output_tokens} output tokens")

        # 拆分 cards
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("markdown"):
                raw = raw[len("markdown"):]
            raw = raw.strip()
        parts = [p.strip() for p in raw.split("---") if p.strip()]
        # 数量校准
        if len(parts) != len(insights):
            print(f"⚠ LLM 返回 {len(parts)} 段, 期望 {len(insights)} 段; 部分降级")
            # 取已有的, 不足的补模板
            cards = parts + render_cards_template(insights[len(parts):])
            return cards[:len(insights)]
        return parts
    except Exception as e:
        print(f"✗ LLM 渲染失败: {e}; 降级模板")
        return render_cards_template(insights)


def summarize_today_llm(insights: list) -> str:
    """≤12 字总结."""
    if not insights:
        return "数据不足"
    try:
        import anthropic
    except ImportError:
        return summarize_today_template(insights)

    if not os.environ.get("ANTHROPIC_API_KEY"):
        return summarize_today_template(insights)

    obs_list = [i.get("observation", "") for i in insights[:5]]
    user_prompt = "## 今日 Insight\n" + "\n".join(f"- {o}" for o in obs_list) + "\n\n请输出 ≤12 字中文总结."

    try:
        client = anthropic.Anthropic()
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=64,
            temperature=0.3,
            system=[{
                "type": "text",
                "text": SUMMARY_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }],
            messages=[{"role": "user", "content": user_prompt}],
        )
        text = response.content[0].text.strip().strip('"').strip("'").strip("。")
        # 长度兜底
        if len(text) > 18:
            text = text[:12]
        return text or summarize_today_template(insights)
    except Exception as e:
        print(f"✗ summary LLM 失败: {e}; 降级模板")
        return summarize_today_template(insights)


def summarize_today_template(insights: list) -> str:
    if not insights:
        return "数据不足"
    top = insights[0]
    obs = top.get("observation", "")
    return obs[:12] if obs else "需关注"


# -------- Step 3: Chart Spec (无 LLM) --------

def load_progression(pdir: Path) -> list:
    f = pdir / "progression.csv"
    if not f.exists():
        return []
    rows = []
    with open(f, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for r in reader:
            rows.append({
                "day": int(r["day"]),
                "raw": float(r["raw_progression"]),
                "effective": float(r["effective_progression"]),
            })
    return rows


def load_surveys(pdir: Path) -> list:
    f = pdir / "surveys.jsonl"
    if not f.exists():
        return []
    rows = []
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_ema(pdir: Path) -> list:
    f = pdir / "ema.jsonl"
    if not f.exists():
        return []
    rows = []
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def load_notes(pdir: Path) -> list:
    f = pdir / "notes.jsonl"
    if not f.exists():
        return []
    rows = []
    with open(f, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def aggregate_ema_daily(ema: list) -> list:
    """按日聚合 EMA mood 取均值."""
    by_day = defaultdict(list)
    for e in ema:
        if e.get("mood") is not None:
            by_day[e["day"]].append(e["mood"])
    daily = []
    for day in sorted(by_day):
        vals = by_day[day]
        daily.append({"day": day, "mood_mean": round(sum(vals) / len(vals), 2)})
    return daily


def find_linked_insight(insights: list, keywords: list) -> str:
    """根据关键字找到对应 insight id."""
    for ins in insights:
        text = (ins.get("observation", "") + " " + ins.get("clinical_implication", "") +
                " ".join(ins.get("supporting_facts", []) or []))
        text = text.lower()
        if any(k.lower() in text for k in keywords):
            return ins.get("id", "")
    return ""


def build_charts(all_insights: list, progression: list, surveys: list, ema: list) -> list:
    """生成 chart specs. 至少 3 类: progression / surveys / EMA."""
    charts = []

    # Chart 1: progression 曲线
    if progression:
        charts.append({
            "id": "chart_001",
            "linked_insight": find_linked_insight(all_insights, ["progression", "进展", "stepwise"]),
            "type": "line",
            "title": "疾病进展 30 天曲线",
            "x_axis": "day",
            "y_axis": "effective_progression",
            "data": [{"day": r["day"], "value": r["effective"]} for r in progression],
            "annotations": [
                {"type": "hline", "value": 0.0, "label": "baseline"},
                {"type": "hline", "value": 0.5, "label": "mild threshold"},
                {"type": "hline", "value": 0.8, "label": "moderate threshold"},
            ],
        })

    # Chart 2: MMSE / MoCA / PHQ-9 纵向
    if surveys:
        charts.append({
            "id": "chart_002",
            "linked_insight": find_linked_insight(all_insights, ["mmse", "moca", "认知"]),
            "type": "multiline",
            "title": "MMSE / MoCA 纵向轨迹",
            "x_axis": "day",
            "y_axis": "score",
            "data": [
                {"day": s["day"], "mmse": s.get("mmse_estimate"), "moca": s.get("moca_estimate")}
                for s in surveys
            ],
            "annotations": [
                {"type": "hline", "value": 24, "label": "MMSE MCI cutoff"},
                {"type": "hline", "value": 26, "label": "MoCA normal cutoff"},
            ],
        })

        charts.append({
            "id": "chart_003",
            "linked_insight": find_linked_insight(all_insights, ["phq", "抑郁", "depression"]),
            "type": "line",
            "title": "PHQ-9 抑郁筛查轨迹",
            "x_axis": "day",
            "y_axis": "phq9",
            "data": [{"day": s["day"], "value": s.get("phq9")} for s in surveys],
            "annotations": [
                {"type": "hline", "value": 5, "label": "mild"},
                {"type": "hline", "value": 10, "label": "moderate"},
                {"type": "hline", "value": 15, "label": "moderately severe"},
            ],
        })

    # Chart 3: EMA mood 30 天
    daily_mood = aggregate_ema_daily(ema)
    if daily_mood:
        baseline = (sum(d["mood_mean"] for d in daily_mood[:7]) / max(1, len(daily_mood[:7])))
        charts.append({
            "id": "chart_004",
            "linked_insight": find_linked_insight(all_insights, ["mood", "情绪", "ema"]),
            "type": "line",
            "title": "EMA mood 30 天日均",
            "x_axis": "day",
            "y_axis": "mood_mean",
            "data": [{"day": d["day"], "value": d["mood_mean"]} for d in daily_mood],
            "annotations": [
                {"type": "hline", "value": round(baseline, 2), "label": "first-week baseline"},
                {"type": "hline", "value": 4, "label": "low-mood threshold"},
            ],
        })

    return charts


def link_cards_to_charts(rendered_cards: list, primary: list, charts: list) -> list:
    """把 markdown card 和 chart id 关联."""
    out = []
    for i, card in enumerate(rendered_cards):
        ins = primary[i] if i < len(primary) else {}
        ins_id = ins.get("id", "")
        linked = [c["id"] for c in charts if c.get("linked_insight") == ins_id]
        out.append({
            "insight_id": ins_id,
            "agent": ins.get("agent", ""),
            "alert_level": ins.get("alert_level"),
            "confidence": ins.get("confidence", 0),
            "card": card,
            "linked_charts": linked,
        })
    return out


# -------- Helpers --------

def safe_load_insights(pdir: Path, name: str) -> list:
    f = pdir / name
    if not f.exists():
        print(f"⚠ {f.name} 不存在, 用空 list")
        return []
    try:
        data = json.loads(f.read_text(encoding="utf-8"))
        # PhysioAgent 输出格式: {patient_id, agent, ..., insights: [...]}
        if isinstance(data, dict) and "insights" in data:
            return data["insights"]
        if isinstance(data, list):
            return data
        print(f"⚠ {name} 格式异常")
        return []
    except Exception as e:
        print(f"✗ 读 {name} 失败: {e}")
        return []


def build_medical_history(persona: dict) -> str:
    age = persona.get("age", "?")
    gender_map = {"M": "男", "F": "女"}
    gender = gender_map.get(persona.get("gender"), "?")
    edu = persona.get("education_years", "?")
    pattern = persona.get("progression_pattern", "?")
    cr = persona.get("cognitive_reserve_factor", 1.0)
    cr_label = "强 (掩盖症状)" if cr < 0.8 else "中等" if cr < 1.1 else "弱 (早期可见)"
    bpsd = persona.get("bpsd_episodes_total", 0)
    return (
        f"{age} 岁{gender}性, 教育 {edu} 年, 进展模式 {pattern}, "
        f"认知储备 {cr:.2f} ({cr_label}), BPSD 事件累计 {bpsd} 次."
    )


def build_session_recap(notes: list) -> str:
    if not notes:
        return "(无历史诊疗记录)"
    last = notes[-1]
    day = last.get("day", "?")
    text = last.get("text", "")
    template = last.get("template", "")
    return f"Day {day} 诊疗记录 ({template}): {text}"


# -------- 主流程 --------

def run_narrator(patient_id: str, save: bool = True) -> dict:
    pdir = DATA_V2 / patient_id
    if not pdir.exists():
        print(f"✗ 没找到 {pdir}")
        return {}

    # 读 persona
    persona_file = pdir / "persona.json"
    persona = json.loads(persona_file.read_text(encoding="utf-8")) if persona_file.exists() else {"patient_id": patient_id}

    # 读三个 agent insights (容错)
    physio = safe_load_insights(pdir, "insights_physio.json")
    behavior = safe_load_insights(pdir, "insights_behavior.json")
    clinical = safe_load_insights(pdir, "insights_clinical.json")

    print(f"→ {patient_id}: physio={len(physio)} behavior={len(behavior)} clinical={len(clinical)}")

    # Step 1: Threader
    threaded = thread_insights(physio, behavior, clinical)
    primary = threaded["primary"][:5]  # top 5
    secondary = threaded["secondary"]
    print(f"→ Threader: primary={len(primary)} secondary={len(secondary)}")

    # 读 chart 数据
    progression = load_progression(pdir)
    surveys = load_surveys(pdir)
    ema = load_ema(pdir)
    notes = load_notes(pdir)

    # Step 2: 渲染 cards (LLM 1 次)
    rendered_cards = render_cards_llm(primary) if primary else []

    # Step 3: 建 charts (无 LLM)
    charts = build_charts(threaded["all"], progression, surveys, ema)
    print(f"→ Charts: {len(charts)} 张")

    # 关联 cards 与 charts
    insights_block = link_cards_to_charts(rendered_cards, primary, charts)

    # summary today (LLM 2 次)
    summary_today = summarize_today_llm(threaded["all"])

    # 元信息
    medical_history = build_medical_history(persona)
    session_recap = build_session_recap(notes)
    report_day = persona.get("n_days", 30)

    dashboard = {
        "patient_id": patient_id,
        "report_day": report_day,
        "medical_history": medical_history,
        "session_recap": session_recap,
        "summary_today": summary_today,
        "patient_data_insights": insights_block,
        "secondary_insights": [
            {
                "id": i.get("id"),
                "agent": i.get("agent"),
                "observation": i.get("observation"),
                "clinical_implication": i.get("clinical_implication"),
                "confidence": i.get("confidence", 0),
                "alert_level": i.get("alert_level"),
            }
            for i in secondary
        ],
        "charts": charts,
        "meta": {
            "primary_n": len(primary),
            "secondary_n": len(secondary),
            "charts_n": len(charts),
            "agent_counts": {
                "physio": len(physio),
                "behavior": len(behavior),
                "clinical": len(clinical),
            },
        },
    }

    if save:
        out_json = pdir / "dashboard.json"
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(dashboard, f, ensure_ascii=False, indent=2)
        print(f"✓ dashboard.json: {out_json}")

        out_md = pdir / "report.md"
        out_md.write_text(render_report_md(dashboard), encoding="utf-8")
        print(f"✓ report.md: {out_md}")

    return dashboard


def render_report_md(d: dict) -> str:
    """生成人类可读 markdown 报告."""
    lines = []
    lines.append(f"# MIND Narrative Dashboard — {d['patient_id']} (Day {d['report_day']})")
    lines.append("")
    lines.append(f"> **今日总结**: {d['summary_today']}")
    lines.append("")

    lines.append("## 病史摘要")
    lines.append(d["medical_history"])
    lines.append("")

    lines.append("## 上次诊疗记录")
    lines.append(d["session_recap"])
    lines.append("")

    lines.append("## 核心 Insight (Primary)")
    if d["patient_data_insights"]:
        for item in d["patient_data_insights"]:
            lines.append(item["card"])
            if item.get("linked_charts"):
                lines.append("")
                lines.append(f"_关联图表_: {', '.join(item['linked_charts'])}  ")
                lines.append(f"_来源_: {item.get('agent', '?')} · confidence={item.get('confidence', 0):.2f}")
            lines.append("")
            lines.append("---")
            lines.append("")
    else:
        lines.append("(无 primary insight)")
        lines.append("")

    if d.get("secondary_insights"):
        lines.append("## 次要观察 (Secondary)")
        for s in d["secondary_insights"]:
            lines.append(f"- **{s.get('observation','')}** "
                         f"({s.get('agent','?')} · conf={s.get('confidence',0):.2f})")
            ci = s.get("clinical_implication") or ""
            if ci:
                lines.append(f"  - {ci}")
        lines.append("")

    lines.append("## 图表清单")
    for c in d.get("charts", []):
        lines.append(f"- **{c['id']}** · {c['title']} · linked_insight={c.get('linked_insight') or '(none)'}")
    lines.append("")

    meta = d.get("meta", {})
    lines.append("## 元信息")
    lines.append(f"- primary_n: {meta.get('primary_n')}")
    lines.append(f"- secondary_n: {meta.get('secondary_n')}")
    lines.append(f"- charts_n: {meta.get('charts_n')}")
    lines.append(f"- agent_counts: {meta.get('agent_counts')}")
    lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    pid = sys.argv[1] if len(sys.argv) > 1 else "P02"
    run_narrator(pid)
