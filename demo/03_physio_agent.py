"""PhysioAgent — LLM 把 DataFact 转成临床 Insight
输入: facts.json (Analyzer 输出) + persona.json + KnowledgeStore
输出: insights.json (两段式临床洞察)
"""

import sys, json, os
from pathlib import Path
import anthropic

# 接 AD 项目的 KnowledgeStore
sys.path.insert(0, "/Users/wenshaoyue/Desktop/research/AD")
from knowledge.knowledge_store import KnowledgeStore

ROOT = Path("/Users/wenshaoyue/Desktop/research")
DATA_V2 = ROOT / "AD MIND" / "data_v2"


PHYSIO_AGENT_SYSTEM_PROMPT = """你是一位资深生理信号临床专家，相当于神经内科医生 + 康复治疗师 + 言语治疗师的合体。你的任务是把统计 Analyzer 抽出的传感器事实，结合医学知识，转化为有临床意义的 Insight。

## 输入
你会收到:
1. DataFact 清单（已经统计学过滤过, 都是显著的, 含 z-score / r 值 / p 值）
2. 患者档案（年龄/教育/进展模式/认知储备）
3. 检索好的医学知识片段

## 输出格式 (严格 JSON 数组)
每条 Insight 包含:
{
  "id": "ins_physio_NNN",
  "observation": "客观传感器观察的一句话总结 (≤30字)",
  "clinical_implication": "临床含义 (≤50字, 必须基于知识库)",
  "domain": "biological|behavioral|temporal",
  "supporting_facts": ["fact 索引或 entity 名"],
  "confidence": 0.0-1.0,
  "differential": "需要鉴别诊断的项 (如有)"
}

## 推理原则
1. 不要重复 fact 原文，要做综合 (synthesize)
2. 临床含义必须基于知识库, 不能编造机制
3. 如证据不足就只给 observation, clinical_implication 留空
4. confidence 反映知识库证据等级 + fact 一致性
5. 不直接做分期判断 (那是 ClinicalAgent 的事)
6. 多个 fact 指向同一现象时合并为一条 Insight

## 关键鉴别清单
- 步态变异 ↑: AD vs PD vs 老年正常
- HRV 降: AD vs 心血管疾病 vs 药物影响
- EDA 反应性 ↑: AD-BPSD vs 焦虑 vs 环境刺激

## 输出
仅输出 JSON 数组, 不要任何解释文字, 不要 ```json``` 代码块.
"""


def build_user_prompt(facts: list, persona: dict, kb_text: str) -> str:
    facts_text = []
    for i, f in enumerate(facts, 1):
        facts_text.append(f"  [{i}][{f['fact_type']}] {f['template_text']}")

    return f"""## 患者档案
- ID: {persona['patient_id']}
- 年龄: {persona['age']} 岁, {('男' if persona['gender']=='M' else '女')}性
- 教育: {persona['education_years']} 年
- 认知储备: {persona['cognitive_reserve_factor']:.2f} ({'强(掩盖症状)' if persona['cognitive_reserve_factor']<0.8 else '中等' if persona['cognitive_reserve_factor']<1.1 else '弱(早期可见)'})
- 进展模式: {persona['progression_pattern']}
- BPSD 倾向: {persona.get('bpsd_prone', False)}
- BPSD 事件总数: {persona.get('bpsd_episodes_total', 0)}

## DataFact 清单 (Analyzer 输出, 已过滤显著)
{chr(10).join(facts_text)}

## 相关医学知识
{kb_text or '(知识库返回空, 仅基于通用临床推理)'}

## 任务
基于以上, 输出 Insight JSON 数组."""


def run_physio_agent(patient_id: str, save: bool = True) -> list:
    pdir = DATA_V2 / patient_id

    # 1. 读 facts
    facts_file = pdir / "facts.json"
    if not facts_file.exists():
        print(f"✗ 没找到 {facts_file} — 先跑 02_analyzer.py")
        return []
    facts = json.loads(facts_file.read_text())

    # 2. 读 persona
    persona = json.loads((pdir / "persona.json").read_text())

    # 3. 路由: 只取 imu/ppg/eda/audio (PhysioAgent 不要 EMA/survey)
    physio_facts = [f for f in facts if f["modality"] in ["imu", "ppg", "eda", "audio"]]
    print(f"→ {patient_id}: 总 {len(facts)} fact, PhysioAgent 接收 {len(physio_facts)} 条")

    # 4. KB 查询
    kb = KnowledgeStore()
    kb_text = kb.query(
        modalities=["imu", "ppg", "eda"],
        min_evidence="C",
        max_entries=8,
    )

    # 5. 构造 prompt
    user_prompt = build_user_prompt(physio_facts, persona, kb_text)

    # 6. 调 Claude
    client = anthropic.Anthropic()
    print(f"→ 调用 Claude (input ~{len(user_prompt)} chars + system ~{len(PHYSIO_AGENT_SYSTEM_PROMPT)} chars)")
    response = client.messages.create(
        model="claude-sonnet-4-5-20250929",
        max_tokens=2048,
        temperature=0.2,
        system=[{
            "type": "text",
            "text": PHYSIO_AGENT_SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": user_prompt}],
    )

    raw = response.content[0].text
    print(f"→ 收到 {response.usage.input_tokens} input + {response.usage.output_tokens} output tokens")

    # 7. 解析
    try:
        # 处理可能有 ```json``` 包裹
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

    print(f"\n=== PhysioAgent 输出 — {patient_id} ===")
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
        out = pdir / "insights_physio.json"
        with open(out, "w", encoding="utf-8") as f:
            json.dump({
                "patient_id": patient_id,
                "agent": "PhysioAgent",
                "model": "claude-sonnet-4-5-20250929",
                "input_facts_n": len(physio_facts),
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
    run_physio_agent(pid)
