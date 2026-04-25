# P01 患者 30 天监测报告 (医生版)

> 由 AD MIND Pipeline 生成 — Analyzer + 3 Agents (Physio/Behavior/Clinical) + Narrator

**患者**: P01 (基础: S01_zewei)
**基本信息**: 68 岁男性, 教育 12 年, 认知储备 0.85 (中等), 进展模式: 线性
**评估窗口**: Day 0 → Day 30 (共 30 天)
**生成时间**: 2026-04-25 13:30
**总评**: 🟡 黄色注意 — MCI → mild_AD 倾向

---

## 一、今日核心结论

> **MCI → mild_AD 转化倾向 (ClinicalAgent 置信度 0.78)**
>
> 多模态指标一致显示认知-行为-自主神经三方位协同恶化。建议立即启动综合非药物干预 + 转诊做 p-tau217 与 MRI 确认 AD 病理。

---

## 二、四张关键证据卡

### 🟡 卡 1: 认知-步态联合退化
- **步速 30 天持续下降至 0.78 m/s** (基线 1.05)
- **双任务变异性升至 8.5%** (基线 2.3%), 双任务代价显著
- 符合 Buracchio 2010 描述的 AD 前驱期步速拐点
- 符合 Verghese 2013 MCR (运动认知衰退综合征) 预诊断标准
- 依据 Insight: `ins_physio_001`, `ins_physio_002`

### 🟡 卡 2: 情绪-自主神经协同恶化
- **PHQ-9 抑郁分** 1.7 → 9.9 (mild → moderate 抑郁)
- **EMA 情绪** 30 天单调下降 (6.3 → 2.0/10, r=-0.91)
- **HRV** 下降 28%, EDA 反应性峰值 z=+9.6
- 三模态同向恶化, 与 AD 共病抑郁 (患病率 30-50%) + BPSD 焦虑前驱症状一致
- 依据 Insight: `ins_behavior_001`, `ins_behavior_002`, `ins_physio_003`, `ins_physio_004`

### 🔴 卡 3: BPSD 事件已成模式
- **Day 24** 出现 **45 分钟徘徊事件** (13:00)
- **Day 28** 出现 **30 分钟激越事件** (14:00)
- 两次发作均在午后, 与日落综合征前置时段一致
- 必须立即启动非药物干预防止恶化
- 依据 Insight: `ins_behavior_004`

### 🟡 卡 4: ClinicalAgent 综合判断
- **MMSE 30 → 11.2** (4 周, 速率异常, Δ = -18.8)
- **MoCA 22.9 → 21.4** (同期仅降 1.5, 提示评估工具差异)
- **强烈建议**:
  - 血液 **p-tau217** 检测确认 AD 病理
  - **头颅 MRI** 排除血管性病变
  - 神经心理详细评估

---

## 三、Analyzer 输出统计 (34 条 fact)

| Fact 类型 | 数量 | 模态分布 |
|---|---:|---|
| outlier (异常值) | 8 | imu 4, eda 2, ppg 2 |
| trend (30 天趋势) | 22 | imu 8, ppg 4, eda 4, ema 4, audio 2 |
| comparison (对比) | 3 | survey (MMSE/MoCA/PHQ-9) |
| difference (任务差) | 1 | dtc (双任务代价) |

**最显著的 5 条 fact (按 severity 排序)**:
1. `severity=1.00` MMSE 由 30.0 变化至 11.2 (Δ=-18.8)
2. `severity=1.00` EDA 变异异常升高至 163.52 (基线 50.63±11.82, z=+9.6)
3. `severity=0.95` EDA 基线 30 天下降趋势 (1912.68 → 1596.43, r=-0.95)
4. `severity=0.93` EMA 焦虑 30 天上升趋势 (1.7 → 6.0/10, r=+0.93)
5. `severity=0.91` EMA 情绪 30 天下降趋势 (6.3 → 2.0/10, r=-0.91)

---

## 四、3 个 Agent 输出 Insight (15 条)

### PhysioAgent (6 条 Insight)
- `ins_physio_001` 🟡 步速 30 天持续下降至 0.78 m/s (置信度 0.88)
- `ins_physio_002` 🟡 双任务步态变异升至 8.5% (置信度 0.85)
- `ins_physio_003` 🟡 HRV 30 天下降 28% (置信度 0.79)
- `ins_physio_004` 🟡 EDA 单点峰值 z=+9.6 (置信度 0.83)
- `ins_physio_005` 平衡站立 SVM 30 天上升 (置信度 0.72)
- `ins_physio_006` EDA 基线下降 17% (置信度 0.65)

### BehaviorAgent (5 条 Insight)
- `ins_behavior_001` 🟡 EMA 情绪单调下降 (置信度 0.85)
- `ins_behavior_002` 🟡 EMA 焦虑上升 (置信度 0.82)
- `ins_behavior_003` EMA 睡眠下降 36% (置信度 0.76)
- `ins_behavior_004` 🔴 Day 24 徘徊 + Day 28 激越 (置信度 0.91)
- `ins_behavior_005` EMA 精力下降 + 重复手部动作 (置信度 0.74)

### ClinicalAgent (1 条综合 Insight)
- `ins_clinical_overall` 🟡 MCI → mild_AD 倾向, 置信度 0.78

---

## 五、干预优先级

| 干预 | 紧迫度 | 依据 |
|---|---|---|
| **安全监控** (GPS + 家属预警) | 🔴 立即 | Day 24 已出现 45 min 徘徊 |
| **音乐疗法** | 本周内 | EMA mood 下降 + EDA 反应性高 (B 级证据) |
| **认知训练** | 本周内 | MMSE 大幅下降, 个性化训练可减缓进展 |
| **睡眠卫生** | 本周内 | EMA 睡眠下降, BPSD 防控基础 |

---

## 六、鉴别诊断关注

1. **AD vs 路易体痴呆 (DLB)**: 需观察是否有视幻觉、REM 行为障碍、运动症状波动
2. **AD vs 血管性痴呆 (VaD)**: 需结合既往脑血管事件史、血管性危险因素
3. **原发抑郁 vs AD 共病抑郁**: 抗抑郁治疗反应性可作鉴别参考

---

## 七、推理链可追溯

每一条 Insight 都引用了 Analyzer 的 fact_id 和 KnowledgeStore 的 knowledge_id。
医生可反查任意结论 → 找到原始数值 + 文献依据。

例如 `ins_physio_001`:
```
观察: 步速 30 天持续下降, 跌至 0.78 m/s
└── 来自 fact: F03 + F05 (Analyzer 的 trend + outlier 检测)
└── 引用知识: SENSOR_IMU_001 (步速 AD 标志物) + NORM_GAIT_001 (老年步速常模)
└── 文献: Buracchio 2010, Verghese 2013
```

---

*由 AD MIND Pipeline v0.1 生成 — Generator v2.1 → Analyzer (34 facts) → 3 Agents (15 insights) → Narrator → 报告*
