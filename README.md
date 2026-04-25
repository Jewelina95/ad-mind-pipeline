# AD MIND Pipeline

> 多模态可穿戴 AD 监测系统 — 基于 MIND 框架, 把合成数据 + 真实 baseline + 专家知识库, 通过 Analyzer + 3 LLM Agents + Narrator 的链路, 转化为可追溯的临床报告。

🌐 **公开网页**: https://jewelina95.github.io/ad-mind-pipeline/

🤝 **配套生成器**: https://jewelina95.github.io/ad-synthetic-generator/

---

## 系统架构

```
DATA LAYER (输入)                     KNOWLEDGE LAYER
─────────────────                     ──────────────────
generator v2.1                        knowledge/*.json (35 条)
real baseline                         ↑文献 + 采访固化
         │                                    │
         ▼                                    │
   Analyzer (无 LLM)                          │
   • outlier / trend / DTC / extreme          │
         │ DataFact[]                         │
         ▼                                    │
   KnowledgeRouter ──────────────────────────┤
         │ knowledge_text                     │
         ▼                                    │
   ┌────────────────┬────────────────┐        │
   │ PhysioAgent    │ BehaviorAgent  │ ◀──────┤
   │ (LLM 1)        │ (LLM 2, 并发)  │        │
   └────────┬───────┴────────┬───────┘        │
            └────────────────┘                │
                     ▼                        │
            ClinicalAgent (LLM 3) ◀───────────┘
                     │ insight[] (含 supporting_facts)
                     ▼
            Narrator (LLM 4)
                     ▼
        医生版报告 + 家属版简报 + Dashboard
```

---

## 仓库结构

```
.
├── docs/                              # GitHub Pages 公开站点
│   ├── index.html                    # 项目主页
│   ├── method.html                   # 4 层架构详解
│   ├── example.html                  # P01 真实测试结果
│   ├── css/style.css
│   └── data/                         # P01 完整 pipeline 输出 (供网页渲染)
├── demo/                             # Pipeline 实现代码
│   ├── 01_generator_v2.py            # 生成器 v2.1 (与 ad-synthetic-generator 对齐)
│   ├── 02_analyzer.py                # Analyzer: CSV → DataFact[]
│   ├── 03_physio_agent.py            # PhysioAgent (LLM)
│   ├── 04_behavior_agent.py          # BehaviorAgent (LLM)
│   ├── 05_clinical_agent.py          # ClinicalAgent (LLM)
│   ├── 06_narrator.py                # Narrator: insights → 报告
│   ├── 07_run_all.py                 # 端到端 runner
│   └── check_status.py               # 检查所有 patient 完成度
├── data_v2/                          # 生成器输出 (5 患者 × 30 天)
│   ├── manifest.json
│   └── P01..P05/
│       ├── persona.json
│       ├── progression.csv
│       ├── ema.jsonl
│       ├── surveys.jsonl
│       ├── notes.jsonl
│       ├── bpsd_events.jsonl
│       ├── sensor/                   # ⚠ git 忽略 (数据量大, 重新生成即可)
│       ├── facts.json                # ← Analyzer 输出
│       ├── insights_physio.json      # ← PhysioAgent 输出
│       ├── insights_behavior.json    # ← BehaviorAgent 输出
│       ├── insights_clinical.json    # ← ClinicalAgent 输出
│       ├── dashboard.json            # ← Narrator 输出
│       └── report.md                 # ← 医生版报告
├── 系统完整设计_v2.md                # 1466 行完整设计文档
└── README.md                         # (本文件)
```

---

## 快速跑通

```bash
# 0. 装依赖
pip install pandas numpy scipy anthropic

# 1. 设置 API key (用真实 LLM 而非 mock)
export ANTHROPIC_API_KEY=sk-ant-...

# 2. 生成 1 个虚拟患者 30 天数据
python3 demo/01_generator_v2.py P01

# 3. 跑 Analyzer
python3 demo/02_analyzer.py P01

# 4. 一键跑剩余所有步骤 (3 Agents + Narrator)
python3 demo/07_run_all.py P01

# 5. 看输出
ls data_v2/P01/
cat data_v2/P01/report.md
```

---

## 跑通的测试结果

P01 (68 岁男, 教育 12 年, linear 退化模式, 30 天):
- ✅ Generator → 30 天 sensor + EMA + surveys + 2 BPSD 事件
- ✅ Analyzer → **34 条 DataFact** (outlier 8 / trend 22 / comparison 3 / DTC 1)
- ✅ 3 Agents → **15 条 Insight**
- ✅ Narrator → 医生版 + 家属版 + 4 张证据卡

**总评**: 🟡 **MCI → mild_AD 倾向 (置信度 0.78)**

详细输出: 见 [Live Demo 网页](https://jewelina95.github.io/ad-mind-pipeline/example.html)

---

## 设计原则

1. **LLM 不算数** — 所有定量计算 (z-score / DTC / 趋势) 由 Analyzer 完成, Agent 只做临床解读
2. **知识检索由数据驱动** — fact 的 tags 决定查什么知识, 不让 Agent 自由发挥
3. **可追溯** — 每条 insight 必须引用 fact_id + knowledge_id, 医生可反查
4. **个体化** — 用每位患者自己的健康 baseline 做 z-score 标尺, 而非群体常模

---

## 文献来源

35 条知识库 JSON 源自:
- Buracchio 2010 (步速拐点先于 MCI 12.1 年)
- Verghese 2013 (MCR 综合征诊断标准)
- Iaboni 2022 (EDA + HR + ACC 检测 BPSD AUC 0.87)
- Khachiyants 2011 / Canevelli 2016 (日落综合征)
- Collins 2012 (HRV 与 AD 关联)
- Montero-Odasso 2019 (双任务步态)
- Shaffer & Ginsberg 2017 (HRV 标准)
- ...

完整知识 JSON 见: https://github.com/Jewelina95/ad-mind-pipeline/tree/main/data_v2

---

## License

MIT

---

🤖 Generated with [Claude Code](https://claude.com/claude-code)
