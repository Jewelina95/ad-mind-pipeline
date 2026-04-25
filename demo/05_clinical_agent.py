"""ClinicalAgent — LLM 综合诊断 + 干预决策
输入: insights_physio.json + insights_behavior.json + surveys.jsonl + notes.jsonl + persona.json
输出: insights_clinical.json (单个临床综合判断对象)

注意: 本 Agent 不读 facts.json, 只看上两位 Agent 的 Insight, 加上量表 + 月度 note.
"""

import sys, json, os
from pathlib import Path
import anthropic

# 接 AD 项目的 KnowledgeStore
sys.path.insert(0, "/Users/wenshaoyue/Desktop/research/AD")
from knowledge.knowledge_store import KnowledgeStore

ROOT = Path("/Users/wenshaoyue/Desktop/research")
DATA_V2 = ROOT / "AD MIND" / "data_v2"


CLINICAL_AGENT_SYSTEM_PROMPT = """你是高年资神经内科 + 老年科医生，相当于 MDT 团队的主持人。你看 PhysioAgent + BehaviorAgent 的全部 Insight + 量表 + clinical note，做出综合判断。

## 任务
1. AD 分期倾向判断 (SCD/MCI/mild/moderate)
2. 转化风险预测 (3-6 个月预后)
3. 鉴别诊断提醒 (vs DLB / VaD / FTD / PD)
4. 干预决策 (音乐/呼吸/认知训练/用药/转诊)
5. 与金标准对接建议 (何时建议 PET/CSF/血液标志物)

## 关键约束
- ★ 你不能"诊断"，只能"建议倾向" + "需要医生确认"
- 输出必须有置信度，且置信度 < 0.7 时禁止给具体分期 (此时 stage_inclination 必须为 "insufficient")
- 每个判断必须引用 PhysioAgent / BehaviorAgent 的具体 Insight ID
- supporting_insights 不能为空, 至少引用 1 条上游 Insight ID

## 标准遵循
- Jack 2024 Revised AT(N) 框架
- Atri 2024 AA 临床实践指南
- GDS 7 阶段
- NIA-AA 生物学定义

## 鉴别诊断要点
- DLB: 视幻觉 / REM 睡眠行为障碍 / 帕金森样症状 / 波动性认知
- VaD: 阶梯式恶化 / 局灶神经体征 / 血管危险因素
- FTD: 行为人格变化 / 语言障碍先于记忆 / 较年轻
- PD: 静止性震颤 / 运动迟缓 / 步态前倾

## 输出格式 (严格 JSON 单个对象, 不是数组)
{
  "id": "ins_clinical_001",
  "stage_inclination": "normal|scd|mci|mild_ad|moderate_ad|insufficient",
  "stage_confidence": 0.0-1.0,
  "differential_concern": ["与 X 鉴别 — 简短理由", ...],
  "intervention_priority": [
    {"type": "music_therapy|breathing|cognitive_training|medication_review|referral|caregiver_education",
     "urgency": "now|today|this_week",
     "rationale": "..."}
  ],
  "gold_standard_referral": "yes|no|maybe",
  "referral_rationale": "...",
  "supporting_insights": ["ins_physio_NNN", "ins_behavior_NNN", ...],
  "alert_level": "green|yellow|red",
  "summary_chinese": "一段中文总结，给医生看的 (3-5 句话, 包含分期倾向 / 主要证据 / 干预建议 / 鉴别提醒)"
}

## 输出
仅输出 JSON 单个对象, 不要任何解释文字, 不要 ```json``` 代码块, 不要数组包裹.
"""


def _fmt_insights(insights: list, label: str) -> str:
    if not insights:
        return f"  ({label} 无 Insight)"
    lines = []
    for ins in insights:
        ins_id = ins.get("id", "?")
        obs = ins.get("observation", "?")
        ci = ins.get("clinical_implication", "")
        conf = ins.get("confidence", 0)
        diff = ins.get("differential", "")
        line = f"  [{ins_id}] {obs}"
        if ci:
            line += f" → {ci}"
        line += f" (conf={conf:.2f}"
        if diff:
            line += f", 鉴别: {diff}"
        line += ")"
        lines.append(line)
    return "\n".join(lines)


def _fmt_surveys(surveys: list) -> str:
    if not surveys:
        return "  (无量表数据)"
    lines = []
    for s in surveys:
        parts = [f"day={s.get('day', '?')}"]
        for k in ("mmse_estimate", "moca_estimate", "phq9", "gds15", "npi"):
            if k in s:
                parts.append(f"{k}={s[k]}")
        lines.append("  " + ", ".join(parts))
    return "\n".join(lines)


def _fmt_notes(notes: list) -> str:
    if not notes:
        return "  (无月度 note)"
    lines = []
    for n in notes:
        day = n.get("day", "?")
        tpl = n.get("template", "?")
        text = n.get("text", "")
        lines.append(f"  [day {day}, template={tpl}] {text}")
    return "\n".join(lines)


def build_user_prompt(
    physio_insights: list,
    behavior_insights: list,
    surveys: list,
    notes: list,
    persona: dict,
    kb_text: str,
) -> str:
    return f"""## 患者档案
- ID: {persona['patient_id']}
- 年龄: {persona['age']} 岁, {('男' if persona['gender']=='M' else '女')}性
- 教育: {persona['education_years']} 年
- 认知储备: {persona['cognitive_reserve_factor']:.2f} ({'强(掩盖症状)' if persona['cognitive_reserve_factor']<0.8 else '中等' if persona['cognitive_reserve_factor']<1.1 else '弱(早期可见)'})
- 进展模式: {persona['progression_pattern']}
- BPSD 倾向: {persona.get('bpsd_prone', False)}
- BPSD 事件总数: {persona.get('bpsd_episodes_total', 0)}

## PhysioAgent Insight ({len(physio_insights)} 条)
{_fmt_insights(physio_insights, 'PhysioAgent')}

## BehaviorAgent Insight ({len(behavior_insights)} 条)
{_fmt_insights(behavior_insights, 'BehaviorAgent')}

## 量表序列 (surveys.jsonl)
{_fmt_surveys(surveys)}

## 月度 Clinical Note (notes.jsonl)
{_fmt_notes(notes)}

## 相关医学知识 (分期 + 干预)
{kb_text or '(知识库返回空, 仅基于通用临床推理)'}

## 任务
基于以上, 综合判断分期倾向, 给出干预优先级 + 鉴别诊断提醒 + 金标准转诊建议.
仅输出单个 JSON 对象 (见 system_prompt 定义)."""


def _load_jsonl(path: Path) -> list:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            rows.append(json.loads(line))
    return rows


def _load_insights(path: Path, label: str) -> list:
    """读 insights_*.json, 返回 insights 列表. 缺失则 warning + 空 list."""
    if not path.exists():
        print(f"⚠ 警告: 没找到 {path.name} ({label} 输出缺失) — 用空 list 代替")
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("insights", [])


def run_clinical_agent(patient_id: str, save: bool = True) -> dict:
    pdir = DATA_V2 / patient_id

    # 1. 读 persona
    persona_file = pdir / "persona.json"
    if not persona_file.exists():
        print(f"✗ 没找到 {persona_file}")
        return {}
    persona = json.loads(persona_file.read_text(encoding="utf-8"))

    # 2. 读上两位 Agent 的 Insight (允许缺失)
    physio_insights = _load_insights(pdir / "insights_physio.json", "PhysioAgent")
    behavior_insights = _load_insights(pdir / "insights_behavior.json", "BehaviorAgent")

    # 3. 读量表 + note
    surveys = _load_jsonl(pdir / "surveys.jsonl")
    notes = _load_jsonl(pdir / "notes.jsonl")

    print(
        f"→ {patient_id}: physio={len(physio_insights)} insight, "
        f"behavior={len(behavior_insights)} insight, "
        f"surveys={len(surveys)} 行, notes={len(notes)} 行"
    )

    # 4. KB 查询: 分期 + 干预 (medication)
    kb = KnowledgeStore()
    kb_staging = kb.query(category="staging", max_entries=6)
    kb_meds = kb.query(category="medication", max_entries=4)
    kb_text_parts = []
    if kb_staging:
        kb_text_parts.append("### 分期相关\n" + kb_staging)
    if kb_meds:
        kb_text_parts.append("### 干预 / 用药\n" + kb_meds)
    kb_text = "\n\n".join(kb_text_parts)

    # 5. 构造 prompt
    user_prompt = build_user_prompt(
        physio_insights, behavior_insights, surveys, notes, persona, kb_text
    )

    # 6. 调 Claude
    client = anthropic.Anthropic()
    print(
        f"→ 调用 Claude (input ~{len(user_prompt)} chars + system ~{len(CLINICAL_AGENT_SYSTEM_PROMPT)} chars)"
    )
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        temperature=0.2,
        system=[{
            "type": "text",
            "text": CLINICAL_AGENT_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text
    print(
        f"→ 收到 {response.usage.input_tokens} input + {response.usage.output_tokens} output tokens"
    )

    # 7. 解析 (单个对象, 不是数组)
    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        clinical = json.loads(text)
        # 容错: 如果模型仍然返回数组, 取第一个
        if isinstance(clinical, list):
            print("⚠ 模型返回数组, 取第一个元素")
            clinical = clinical[0] if clinical else {}
    except json.JSONDecodeError as e:
        print(f"✗ JSON 解析失败: {e}")
        print("原始输出:")
        print(raw[:1000])
        return {}

    # 8. 置信度兜底: < 0.7 强制 insufficient
    conf = clinical.get("stage_confidence", 0) or 0
    if conf < 0.7 and clinical.get("stage_inclination") not in ("insufficient", None):
        print(f"⚠ stage_confidence={conf:.2f} < 0.7, 强制 stage_inclination → insufficient")
        clinical["stage_inclination"] = "insufficient"

    # 9. 打印
    print(f"\n=== ClinicalAgent 输出 — {patient_id} ===")
    print(f"分期倾向:    {clinical.get('stage_inclination', '?')} (conf={conf:.2f})")
    print(f"警戒等级:    {clinical.get('alert_level', '?')}")
    print(f"金标准转诊:  {clinical.get('gold_standard_referral', '?')} — {clinical.get('referral_rationale', '')}")
    diffs = clinical.get("differential_concern", []) or []
    if diffs:
        print(f"鉴别诊断:")
        for d in diffs:
            print(f"  · {d}")
    interv = clinical.get("intervention_priority", []) or []
    if interv:
        print(f"干预优先级:")
        for it in interv:
            print(f"  · [{it.get('urgency','?')}] {it.get('type','?')} — {it.get('rationale','')}")
    sup = clinical.get("supporting_insights", []) or []
    print(f"引用 Insight: {', '.join(sup) if sup else '(无)'}")
    print(f"\n中文总结:\n  {clinical.get('summary_chinese', '')}")

    if save:
        out = pdir / "insights_clinical.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({
                "patient_id": patient_id,
                "agent": "ClinicalAgent",
                "model": "claude-sonnet-4-5-20250929",
                "input_physio_insights_n": len(physio_insights),
                "input_behavior_insights_n": len(behavior_insights),
                "input_surveys_n": len(surveys),
                "input_notes_n": len(notes),
                "kb_entries_used": kb_text.count("###"),
                "clinical": clinical,
                "tokens": {
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                },
            }, f, ensure_ascii=False, indent=2)
        print(f"\n✓ 写入: {out}")

    return clinical


if __name__ == "__main__":
    pid = sys.argv[1] if len(sys.argv) > 1 else "P02"
    run_clinical_agent(pid)
