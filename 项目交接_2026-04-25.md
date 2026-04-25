# AD 项目对话交接文档

> **日期**: 2026-04-25
> **来源对话**: 与 Claude (Opus 4.7) 的长会话
> **目的**: 新 terminal 接着干 Agent 搭建，本文档是完整上下文
> **作者背景**: 用户 = Aaron (Jewelina95 GitHub账号)

---

# 0. 一句话项目概要

**AD 多智能体可穿戴手套监测系统** — 模仿 MIND (CHI 2026) 的 narrative dashboard 模式，构建 Analyzer→Synthesizer(3 Agent)→Narrator 的 pipeline，使用真实 OpenNeuro 数据集校准的合成患者数据 demo 整套系统。

---

# 1. 项目分布在 4 个目录

```
/Users/wenshaoyue/Desktop/research/
├── AD/                        ← 旧代码 + KB + 数据 (主项目)
│   ├── src/agents/            7 个 Agent stub (旧, 要重构成 3 个)
│   ├── src/skills/            ad_staging.py (旧, 要废弃)
│   ├── knowledge/             ★ 35 条 JSON KB + KnowledgeStore
│   ├── data/baseline 4.8/     真实健康 baseline + reference_ranges
│   ├── 数据库汇总2026.4.18/    李医生给的真实临床 xlsx (10 个时点)
│   └── resources/3.8李医生采访.md  ★ 26 问 + 真实回答
│
├── AD MIND/                   ← 新设计文档 + demo 代码 (本对话产物)
│   ├── 系统完整设计_v2.md      ★ 整体架构设计文档
│   ├── 项目交接_2026-04-25.md  ★ 本文档
│   ├── demo/
│   │   ├── 01_generator_v2.py  生成器 (已完成 + 跑过)
│   │   ├── 02_analyzer.py      ★ Analyzer (已完成, 跑出 31 fact)
│   │   └── 03_physio_agent.py  ★ PhysioAgent (代码 ready, 缺 API key)
│   └── data_v2/                合成数据输出 (5 患者 × 30 天)
│
├── AD open datasets/          ← OpenNeuro 数据集
│   ├── AD相关公开数据集汇总.md  10 个数据集介绍
│   ├── data/                   10 个数据集 git clone (仅 metadata)
│   ├── output/distributions_master.json  ★ 真实分布 (n=112 MMSE)
│   └── scripts/extract_*.py   提取脚本
│
└── AD generator/              ← 自包含生成器项目 (本对话最新)
    ├── README.md              ★ 完整设计报告 (含 P02 案例)
    ├── src/generate_synthetic.py
    └── data/{baseline,distributions,synthetic}/
```

---

# 2. 已完成 (从 0 到现在)

## 2.1 数据准备 ✅

```
✅ 下载 10 个 OpenNeuro 数据集 (metadata)
   - ds004504 (88 EEG AD/FTD/Healthy)
   - ds007427 (138 EEG Lopera Colombia AD/MCI/CTR)
   - ds006095 (71 老年 EEG+EMG+IMU+MOCA)
   - ds004796 (PEARL-Neuro 中年风险)
   - ds002778, ds006036, ds005363, ds005892, ds006466
   - MultiConAD (代码, 数据需另申请)

✅ 提取真实分布 → distributions_master.json
   - MMSE: ctrl μ=29.69, mci μ=22.86, ad μ=17.75 (n=112)
   - MOCA: 老年 μ=27.45 (n=71)

✅ 删 4 个无关数据集 (ds004295/ds004767/ds007671/ds003871)
```

## 2.2 生成器 v2.1 ✅

```
✅ /Users/wenshaoyue/Desktop/research/AD generator/src/generate_synthetic.py
   - 5 patient × 30 day 纵向轨迹
   - 跨模态耦合 (sensor/EMA/survey/note 同 progression)
   - BPSD episode 注入 (依据李医生采访 90% 患病率)
   - 缺失数据 + 运动伪迹 (依据采访 30% 缺失现实)
   - 认知储备 (高教育掩盖症状: edu 16 → reserve 0.65)
   - --days / --patients 命令行参数

✅ 已跑出 5 个虚拟患者:
   P01 linear   edu=12 reserve=0.85 → 2 BPSD
   P02 stepwise edu=6  reserve=1.15 → 1 BPSD ⭐ 案例
   P03 plateau  edu=16 reserve=0.65 → 0 BPSD (高储备验证)
   P04 fluct    edu=9  reserve=1.00 → 1 BPSD
   P05 acute    edu=12 reserve=0.85 → 0 BPSD
```

## 2.3 Analyzer ✅

```
✅ /Users/wenshaoyue/Desktop/research/AD MIND/demo/02_analyzer.py
   - 5 类 fact (outlier/trend/comparison/difference/extreme)
   - 4 模态 (IMU/PPG/EDA/EMA/Survey)
   - 输出 DataFact JSON + facts.json

✅ P02 跑出 31 条 DataFact, 例如:
   - "EMA 情绪 30 天下降 7.0→2.7 (r=-0.90)"
   - "MMSE 由 30→23 (Δ=-7.0)"
   - "balance svm_std z=+18.6"
```

## 2.4 KnowledgeStore ✅ (旧, 已写但 Agent 没用)

```
✅ /Users/wenshaoyue/Desktop/research/AD/knowledge/
   - 35 条 JSON (BPSD/分期/标志物/药物)
   - knowledge_store.py 检索引擎已写好
   - kb.query(modalities=["imu"], min_evidence="C") 可用
```

---

# 3. 当前状态 (你接手时 here)

## 3.1 Pipeline 完成度

```
✅ 数据生成 (生成器 v2.1)        100%
✅ Analyzer (rule-based)         100%
✅ KnowledgeStore                100% (但 Agent 没接)
🟡 PhysioAgent                    90% (代码 ready, 等 API key)
❌ BehaviorAgent                   0%
❌ ClinicalAgent                   0%
❌ Narrator                        0%
❌ React 前端                       0%
❌ End-to-end demo                  0%
```

## 3.2 现在卡在哪

**唯一硬卡点**: ANTHROPIC_API_KEY 没设置

PhysioAgent 代码 (`/Users/wenshaoyue/Desktop/research/AD MIND/demo/03_physio_agent.py`) 已经写完，跑会报：
```
TypeError: Could not resolve authentication method.
Expected either api_key or auth_token to be set.
```

解决：在新 terminal 里 export key:
```bash
export ANTHROPIC_API_KEY='sk-ant-...'
cd "/Users/wenshaoyue/Desktop/research/AD MIND"
python3 demo/03_physio_agent.py P02
```

---

# 4. 下一步计划 (新 terminal 接着干)

## 4.1 立即 (设完 key 就跑)

```bash
# Step 1: 跑 PhysioAgent
cd "/Users/wenshaoyue/Desktop/research/AD MIND"
python3 demo/03_physio_agent.py P02
# 期望输出: 3-6 条 Insight JSON, 写到 P02/insights_physio.json
```

## 4.2 写 BehaviorAgent (~30 分钟)

复制 03_physio_agent.py → 04_behavior_agent.py，改：
- `system_prompt` 改成 BEHAVIOR_AGENT_SYSTEM_PROMPT (在设计文档第 6.2 节)
- `routing` 改成接收 EDA + EMA + 部分 IMU fact
- 关注: BPSD 检测 + 信号消歧 + 日落综合征

```python
# 关键: BehaviorAgent 接收 fact 类型筛选
behavior_facts = [f for f in facts if f["modality"] in ["eda", "ema"]
                  or "anxiety" in f.get("entity","")
                  or "mood" in f.get("entity","")]
```

## 4.3 写 ClinicalAgent (~30 分钟)

复制改造，关键点：
- 输入是**前两个 Agent 的 Insight**（不是 raw fact）
- 加上 survey 和 clinical note
- 输出 stage_inclination + intervention_priority + alert_level

## 4.4 写 Narrator (~30 分钟)

```python
# /Users/wenshaoyue/Desktop/research/AD MIND/demo/05_narrator.py
def generate_dashboard(all_insights, persona):
    return {
        "medical_history": ...,           # persona.json 摘要
        "session_recap": ...,             # 上次 note SOAP 化
        "patient_data_insights": [...],   # 两段式 markdown
        "summary_today": "...",           # ≤12 字
        "charts": [...],                  # JSON spec, React 渲染
    }
```

## 4.5 端到端 demo (~30 分钟)

```python
# /Users/wenshaoyue/Desktop/research/AD MIND/demo/06_run_all.py
patient_id = "P02"

# Step 1: Analyzer
facts = analyzer.discover(patient_dir)

# Step 2: 3 Agent
physio = PhysioAgent(kb).synthesize(filter(facts, ["imu","ppg","eda","audio"]))
behavior = BehaviorAgent(kb).synthesize(filter(facts, ["eda","ema"]))
clinical = ClinicalAgent(kb).synthesize(physio + behavior + survey_facts)

# Step 3: Narrator
dashboard = Narrator().generate(physio + behavior + [clinical], persona)

# Step 4: 写 markdown 报告
write_markdown_report(dashboard, "P02_demo_report.md")
```

---

# 5. 关键设计决策 (背景)

## 5.1 用了几个数据集?

**5 个 OpenNeuro 数据集**做分布对标:
- ds004504 + ds007427 → 联合 n=112 真实患者 MMSE 分布
- ds006095 → n=71 老年 MOCA
- ds004796 + ds002778 备用

**不是 ML 训练**——只是用真实分布数字校准生成器的统计参数。

## 5.2 为什么 30 天不是 1-2 天?

产品最终形态是**长期居家监测**（plan 文件 6 节: "≥6 个月连续佩戴"），1-2 天是门诊形态 A，长期是形态 B。生成器**默认 30 天**给 demo 用，可 `--days 2` 切换形态 A。

**核心原则**: 生成长，使用灵活。30 天能切出任意短窗口；只生成 2 天就回不去。

## 5.3 为什么 3 个 Agent 不是 7 个?

旧设计 7 个 Agent (motor/language/autonomic/emotion/clinical/intervention/care) 严重冗余。**MIND 是单 LLM**，我们扩展成 3 是为了凸显 MDT 多专家但不过度。

```
Motor + Language + Autonomic   →  PhysioAgent
Emotion + 部分 BPSD             →  BehaviorAgent
Clinical + Intervention + Care  →  ClinicalAgent
```

## 5.4 为什么不训 ML?

MIND 论文**0 个训练模型**——纯 rule + LLM。我们 4 个真实 baseline 训 XGBoost 严重过拟合。所以 Analyzer 全是统计公式（z-score / linregress），Agent 全是 LLM prompt + KB 检索。

---

# 6. 文件清单速查

```bash
# 设计文档
/Users/wenshaoyue/Desktop/research/AD MIND/系统完整设计_v2.md
/Users/wenshaoyue/Desktop/research/AD generator/README.md  (含 P02 案例)

# 生成器代码 (推荐用 AD generator/ 自包含版本)
/Users/wenshaoyue/Desktop/research/AD generator/src/generate_synthetic.py

# 已生成数据
/Users/wenshaoyue/Desktop/research/AD generator/data/synthetic/
  ├── P01..P05/persona.json
  ├── P01..P05/progression.csv
  ├── P01..P05/bpsd_events.jsonl
  ├── P01..P05/ema.jsonl
  ├── P01..P05/surveys.jsonl
  ├── P01..P05/notes.jsonl
  └── P01..P05/sensor/dayXX_TASK.csv  (120-150 个 / patient)

# Analyzer 代码 + 输出
/Users/wenshaoyue/Desktop/research/AD MIND/demo/02_analyzer.py
/Users/wenshaoyue/Desktop/research/AD MIND/data_v2/P02/facts.json  (31 条 fact)

# PhysioAgent 代码 (待 API key)
/Users/wenshaoyue/Desktop/research/AD MIND/demo/03_physio_agent.py

# 知识库
/Users/wenshaoyue/Desktop/research/AD/knowledge/
  ├── knowledge_store.py
  ├── staging/, sensors/, clinical/

# 真实分布参考
/Users/wenshaoyue/Desktop/research/AD open datasets/output/distributions_master.json
/Users/wenshaoyue/Desktop/research/AD generator/data/distributions/distributions_master.json (复制)

# 李医生采访 (设计依据!)
/Users/wenshaoyue/Desktop/research/AD/resources/3.8李医生采访.md
```

---

# 7. 关键命令速查

```bash
# 重新生成数据
cd "/Users/wenshaoyue/Desktop/research/AD generator"
python3 src/generate_synthetic.py --days 30 --patients 5

# 跑 Analyzer
cd "/Users/wenshaoyue/Desktop/research/AD MIND"
python3 demo/02_analyzer.py P02

# 跑 PhysioAgent (需先 export key)
export ANTHROPIC_API_KEY='sk-ant-...'
python3 demo/03_physio_agent.py P02

# 检查 KB
python3 -c "
import sys; sys.path.insert(0, '/Users/wenshaoyue/Desktop/research/AD')
from knowledge.knowledge_store import KnowledgeStore
kb = KnowledgeStore()
print(kb.query(modalities=['imu'], min_evidence='C', max_entries=3))
"

# 看 P02 完整数据
ls "/Users/wenshaoyue/Desktop/research/AD generator/data/synthetic/P02/"
cat "/Users/wenshaoyue/Desktop/research/AD generator/data/synthetic/P02/persona.json"
cat "/Users/wenshaoyue/Desktop/research/AD generator/data/synthetic/P02/bpsd_events.jsonl"
```

---

# 8. 用户特别说明的事项

| 何时 | 用户说了什么 | 我的解读 |
|---|---|---|
| 生成器结构改动时 | "你凭什么这么改的?" | **每个改动必须给依据**(李医生采访章节) |
| 写文档位置 | "不要写在 AD project, 写在 AD MIND" | 设计文档放 AD MIND, 代码可以放 AD/AD generator |
| 数据集 | "都做全部一起做" | 用尽量多数据集 (做了 10 个 OpenNeuro) |
| 时间紧迫 | "1 小时完成很多" | 优先级: 跑通 > 完美 |
| 验证设计 | 关注 P03 (高教育) 是否真 0 BPSD | 设计依据要在数据里能验证 |
| 待办 | "我要开另外一个 terminal 去进行 agent 的搭建" | **本文档目的: 让新 terminal 能接着干** |

---

# 9. 已知遗留任务 (没做完的)

```
🟡 GitHub repo + 网页可视化
   - 用户要求建 repo push, 配套 GitHub Pages
   - 460 MB 合成数据需考虑 git LFS 或排除
   - 静态 HTML + Plotly 展示数据源 + 生成效果
   - 本对话**没做完**, 新 terminal 可继续

❌ ADReSS 中文语音数据 (Audio Agent 用)
   - 通过 MultiConAD 作者获取 (建议路径)
   - 或 DementiaBank 学术注册

❌ WearGait-PD 真实 IMU 分布
   - 用户在 Synapse 注册中

❌ 真实进展曲线拟合 (OASIS-3)
   - 当前 5 种 progression 模式是合理猜的
   - 拿到 OASIS-3 后可严格拟合
```

---

# 10. 重要原则 (新 terminal 必须遵守)

1. **生成器/Analyzer/Agent 都要可解释、有依据** — 每个数字、每条规则都能追到李医生采访 / KB / 公开数据
2. **不训练 ML** — 走 MIND 同款 rule + LLM 路线
3. **3 个 Agent 不是 7 个** — 简化结构
4. **Token 优化** — system prompt 用 cache_control 标 ephemeral
5. **prompt 不全量注入** — 用 KnowledgeStore.query() 按需检索
6. **配合 co-design** — 关键模板需让李医生 review (paper method 章节素材)
7. **写代码尽量自包含** — `AD generator/` 已经做到, 后续 Agent 也尽量

---

**文档结束。新 terminal 看完这份就能完整接手。建议入口: 设 API key → 跑 PhysioAgent → 写 BehaviorAgent。**
