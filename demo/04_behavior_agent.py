"""BehaviorAgent — LLM 把 DataFact + BPSD 事件转成行为/情绪 Insight
输入: facts.json + persona.json + bpsd_events.jsonl + KnowledgeStore
输出: insights_behavior.json
"""

import sys, json, os
from pathlib import Path
import anthropic

sys.path.insert(0, "/Users/wenshaoyue/Desktop/research/AD")
from knowledge.knowledge_store import KnowledgeStore

ROOT = Path("/Users/wenshaoyue/Desktop/research")
DATA_V2 = ROOT / "AD MIND" / "data_v2"


BEHAVIOR_AGENT_SYSTEM_PROMPT = """你是一位精神科 + 行为分析专家，专攻 BPSD (痴呆行为与精神症状) 检测和情境消歧。

## 你的核心任务
1. BPSD 检测与分类 (NPI 12 维度)
2. 情绪状态推断 (多模态: EDA + HR + 语音 + 活动 + EMA)
3. 信号消歧: "HR 高是激越还是运动还是访客刺激?"
4. 日落综合征模式识别
5. 激越提前预警 (1-2 小时窗口)

## 信号消歧决策树 (必须遵守)
- HR↑ + EDA↑ + 步态稳定 + 有访客 → 情绪激动 (非病理)
- HR↑ + EDA↑ + 步态不稳 + 下午 4-6 点 → 日落综合征可能
- HR↑ + EDA↓ + 活动增加 → 运动性 (正常)
- HR↑ + EDA↑ + 语音异常 + 独处 → BPSD 激越 (需干预)
- 活动减少 + EMA mood 低 + HRV 异常 → 抑郁

## 输入
1. DataFact 清单 (Analyzer 输出, 已过滤显著, 含 z-score / r 值 / p 值)
2. 患者档案
3. BPSD 事件清单 (day/hour/type/duration)
4. 检索好的 BPSD 知识片段

## 输出格式 (严格 JSON 数组)
每条 Insight 包含:
{
  "id": "ins_behavior_NNN",
  "observation": "客观行为/情绪观察的一句话总结 (≤30字)",
  "clinical_implication": "临床含义 (≤50字, 必须基于知识库)",
  "domain": "psychological|behavioral|social",
  "supporting_facts": ["fact 索引或 entity 名"],
  "confidence": 0.0-1.0,
  "differential": "需要鉴别诊断的项 (如有)"
}

## 推理原则
1. 不要重复 fact 原文，要做综合 (synthesize)
2. 临床含义必须基于知识库, 不能编造机制
3. 如证据不足就只给 observation, clinical_implication 留空
4. confidence 反映知识库证据等级 + fact 一致性
5. 多个 fact 指向同一现象时合并为一条 Insight

## 不要做的事
- 不直接给 BPSD 诊断标签 (那需要医生确认)
- 不预测分期 (ClinicalAgent 的事)
- 不开具体干预方案 (ClinicalAgent 的事)

## 输出
仅输出 JSON 数组, 不要任何解释文字, 不要 ```json``` 代码块.
"""


def build_user_prompt(facts: list, persona: dict, bpsd_events: list, kb_text: str) -> str:
    facts_text = []
    for i, f in enumerate(facts, 1):
        facts_text.append(f"  [{i}][{f['fact_type']}] {f['template_text']}")

    bpsd_text = []
    for e in bpsd_events:
        bpsd_text.append(f"  - day {e.get('day')} hour {e.get('hour')}: {e.get('type')} ({e.get('duration_min')}min, progression={e.get('progression_at_event')})")

    return f"""## 患者档案
- ID: {persona['patient_id']}
- 年龄: {persona['age']} 岁, {('男' if persona['gender']=='M' else '女')}性
- 教育: {persona['education_years']} 年
- 认知储备: {persona['cognitive_reserve_factor']:.2f} ({'强(掩盖症状)' if persona['cognitive_reserve_factor']<0.8 else '中等' if persona['cognitive_reserve_factor']<1.1 else '弱(早期可见)'})
- 进展模式: {persona['progression_pattern']}
- BPSD 倾向: {persona.get('bpsd_prone', False)}
- BPSD 事件总数: {persona.get('bpsd_episodes_total', 0)}

## DataFact 清单 (Analyzer 输出, 已过滤显著)
{chr(10).join(facts_text) if facts_text else '(无)'}

## BPSD 事件
{chr(10).join(bpsd_text) if bpsd_text else '(无记录)'}

## 相关 BPSD / 行为知识
{kb_text or '(知识库返回空, 仅基于通用临床推理)'}

## 任务
基于以上, 输出 Insight JSON 数组."""


def run_behavior_agent(patient_id: str, save: bool = True) -> list:
    pdir = DATA_V2 / patient_id

    facts_file = pdir / "facts.json"
    if not facts_file.exists():
        print(f"✗ 没找到 {facts_file} — 先跑 02_analyzer.py")
        return []
    facts = json.loads(facts_file.read_text())

    persona = json.loads((pdir / "persona.json").read_text())

    behavior_facts = [f for f in facts if
                      f["modality"] in ["eda", "ema"] or
                      "anxiety" in f.get("entity", "") or
                      "mood" in f.get("entity", "") or
                      "phq9" in f.get("entity", "") or
                      "sleep" in f.get("entity", "")]
    print(f"→ {patient_id}: 总 {len(facts)} fact, BehaviorAgent 接收 {len(behavior_facts)} 条")

    bpsd_events = []
    bpsd_file = pdir / "bpsd_events.jsonl"
    if bpsd_file.exists():
        bpsd_events = [json.loads(l) for l in bpsd_file.read_text().strip().split("\n") if l]
    print(f"→ BPSD 事件: {len(bpsd_events)} 条")

    kb = KnowledgeStore()
    kb_text = kb.query(category="bpsd", max_entries=8)

    user_prompt = build_user_prompt(behavior_facts, persona, bpsd_events, kb_text)

    client = anthropic.Anthropic()
    print(f"→ 调用 Claude (input ~{len(user_prompt)} chars + system ~{len(BEHAVIOR_AGENT_SYSTEM_PROMPT)} chars)")
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        temperature=0.2,
        system=[{
            "type": "text",
            "text": BEHAVIOR_AGENT_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text
    print(f"→ 收到 {response.usage.input_tokens} input + {response.usage.output_tokens} output tokens")

    try:
        text = raw.strip()
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
            text = text.strip()
        insights = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"✗ JSON 解析失败: {e}")
        print("原始输出:")
        print(raw[:1000])
        return []

    print(f"\n=== BehaviorAgent 输出 — {patient_id} ===")
    print(f"共 {len(insights)} 条 Insight:\n")
    for i, ins in enumerate(insights, 1):
        print(f"[{i}] {ins.get('observation', '?')}")
        ci = ins.get('clinical_implication', '')
        if ci:
            print(f"     ★ {ci}")
        if ins.get('differential'):
            print(f"     ⚠ 鉴别: {ins['differential']}")
        print(f"     confidence={ins.get('confidence', 0):.2f}, domain={ins.get('domain', '?')}")
        print()

    if save:
        out = pdir / "insights_behavior.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({
                "patient_id": patient_id,
                "agent": "BehaviorAgent",
                "model": "claude-sonnet-4-5-20250929",
                "input_facts_n": len(behavior_facts),
                "bpsd_events_n": len(bpsd_events),
                "kb_entries_used": kb_text.count("###"),
                "insights": insights,
                "tokens": {
                    "input": response.usage.input_tokens,
                    "output": response.usage.output_tokens,
                },
            }, f, ensure_ascii=False, indent=2)
        print(f"✓ 写入: {out}")

    return insights


if __name__ == "__main__":
    pid = sys.argv[1] if len(sys.argv) > 1 else "P02"
    run_behavior_agent(pid)
