# GraphSkill

**面向 LLM Agent 的拓扑感知过程性知识路由中间件**

---

## 项目简介

GraphSkill 是一个位于 LLM Agent 核心大脑（LLM）与外部工具/环境之间的智能技能路由中间件。它将离散的 `SKILL.md` 文件转换为具备拓扑关系的知识图谱，根据运行时上下文动态组装最小必要技能子集，确保输出技能集合零冲突、高内聚，并基于遥测数据实现图谱自我进化。

### 核心价值

| 传统方案痛点 | GraphSkill 解决方案 |
|--------------|---------------------|
| 全量技能加载导致 Token 浪费 | 按需加载最小必要技能子集 |
| 纯向量检索忽略拓扑依赖 | 混合召回 + 图扩展 + 冲突剪枝 |
| 互斥技能同时注入导致逻辑死锁 | MWIS 算法确保零冲突输出 |
| 静态图谱无法适应运行时变化 | EWMA 可靠性衰减 + 隐性边发现 |

### 技术亮点

1. **拓扑感知混合召回**：语义种子召回 + 图扩展（1-hop）
2. **MWIS 冲突剪枝**：最大权重独立集贪心算法，O(n log n) 复杂度
3. **VR-First 架构**：Vector-RAG 作为保底基线，图增强层在其之上优化
4. **运行时自我进化**：基于遥测数据的边权重动态调整

---

## 系统架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GraphSkill Architecture                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Offline Layer (离线层)                        │   │
│  │  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐  │   │
│  │  │  Ingestion      │    │  Graph Builder  │    │  Embedding      │  │   │
│  │  │  Pipeline       │───▶│  (Neo4j)        │◀───│  Service        │  │   │
│  │  │  (SKILL.md)     │    │  + Vector Store │    │  (Sentence      │  │   │
│  │  └─────────────────┘    │  (Milvus)       │    │   Transformers) │  │   │
│  │                         └─────────────────┘    └─────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                        Online Layer (在线层)                         │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │                    Routing Gateway (VR-First)                │    │   │
│  │  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │    │   │
│  │  │  │ VR Baseline  │─▶│ Graph Enhance│─▶│ MWIS Pruning     │   │    │   │
│  │  │  │ (Milvus Top-K)│  │ (Scoring)    │  │ (Conflict-Free)  │   │    │   │
│  │  │  └──────────────┘  └──────────────┘  └──────────────────┘   │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  │                              │                                      │   │
│  │                              ▼                                      │   │
│  │  ┌─────────────────────────────────────────────────────────────┐    │   │
│  │  │              Context Assembler & Token Budget                │    │   │
│  │  └─────────────────────────────────────────────────────────────┘    │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                    │                                       │
│                                    ▼                                       │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                     Telemetry Layer (遥测层)                         │   │
│  │  • EWMA Reliability Decay  • Implicit Edge Discovery  • Redis Cache │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 目录结构

```
GraphSkill/
├── README.md                    # 本文件（项目总览）
├── ROADMAP.md                   # 项目路线图与阶段规划
├── Makefile                     # 构建与测试快捷命令
├── .gitignore                   # Git 忽略规则
│
├── src/python/                  # Python 源码（核心库）
│   ├── graphskill/
│   │   ├── core/                # 核心数据模型与常量
│   │   ├── ingestion/           # 离线知识图谱构建管道
│   │   ├── routing/             # 在线路由网关（VR-First 架构）
│   │   ├── storage/             # 存储层（Neo4j + Milvus + Redis）
│   │   ├── runtime/             # Agent 运行时注入层
│   │   └── telemetry/           # 遥测与自我进化模块
│   └── tests/                   # 单元测试、集成测试、E2E 测试
│
├── scripts/                     # 实验脚本与工具
│   ├── run_real_experiment.py   # SkillsBench 真实执行实验
│   ├── run_paper_experiment_v5.py  # SWE-bench V5 实验
│   ├── run_swebench_experiment.py  # SWE-bench Plan B 实验
│   ├── run_multi_benchmark_experiment.py  # 多基准统一实验
│   ├── generate_skills_for_benchmark.py   # 技能数据生成
│   ├── generate_paper_report.py           # 论文报告生成
│   └── benchmarks/                # 基准测试适配器
│       ├── base_adapter.py
│       ├── skillsbench_adapter.py
│       ├── swebench_adapter.py
│       ├── toolbench_adapter.py
│       └── webarena_adapter.py
│
├── data/                        # 实验数据（详见 data/README.md）
│   ├── exp-glm5-skillsbench/    # GLM-5.1 × SkillsBench 实验
│   ├── exp-deepseek_v4_flash-skillsbench/
│   ├── exp-deepseek_v4_pro-skillsbench/
│   ├── exp-qwen3_coder_flash-skillsbench/
│   ├── exp-glm5-swebench_v5/
│   ├── exp-deepseek_v4_flash-swebench_v5/
│   ├── exp-glm5-swebench_planb/
│   ├── harbor-results/          # 原始 Harbor 执行结果
│   ├── resources/               # 共享资源（技能数据、数据集等）
│   ├── old-backup/              # 旧版数据备份
│   └── archive/                 # 已废弃实验
│
├── paper/                       # 论文撰写
│   ├── mypaper/                 # LaTeX 论文源码
│   │   ├── main.tex
│   │   ├── sections/            # 各章节 .tex 文件
│   │   └── figures/             # 论文配图
│   ├── md-draft/                # Markdown 草稿
│   └── figures/                 # 原始图表设计
│
├── docs/                        # 架构设计文档（RFC 系列）
│   ├── RFC-00-architecture-overview.md
│   ├── RFC-01-data-specification-storage-layer.md
│   ├── RFC-02-offline-ingestion-pipeline.md
│   ├── RFC-03-online-routing-gateway.md
│   ├── RFC-04-runtime-integration-layer.md
│   ├── RFC-05-telemetry-self-evolution-feedback.md
│   ├── RFC-06-performance-security-high-availability.md
│   ├── RFC-07-api-interface-specification.md
│   ├── RFC-08-data-structures-schema.md
│   ├── RFC-09-deployment-operations.md
│   ├── RFC-10-testing-quality-assurance.md
│   └── RFC-11-security-permission-model.md
│
├── plans/                       # 实验与开发计划
│   ├── multi_benchmark_experiment_plan.md
│   ├── phase_6f_vr_first_architecture.md
│   ├── swebench_plan_b_v5_based.md
│   └── ...
│
├── schemas/                     # JSON Schema 定义
│   ├── json/routing-request-v1.json
│   ├── json/routing-response-v1.json
│   ├── json/skill-manifest-v1.json
│   └── json/skill-node-v1.json
│
├── configs/                     # 配置文件
│   ├── experiment_config.yaml
│   ├── env.example              # 环境变量模板
│   └── env.test                 # 测试环境配置
│
└── deploy/                      # 部署配置
    └── docker/docker-compose.test.yml
```

---

## 快速开始

### 环境要求

- **Python**: 3.11+
- **Neo4j**: 5.x（图数据库）
- **Milvus**: 2.4+（向量数据库）
- **Redis**: 7.x（缓存）
- **Node.js**: 20+（前端/工具链）

### 安装

```bash
# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
cd src/python
pip install -e ".[dev]"

# 安装 ruff（格式化和 linting）
pip install ruff
```

### 运行测试

```bash
# 单元测试
cd src/python
pytest tests/unit/

# 集成测试
pytest tests/integration/

# E2E 测试
pytest tests/e2e/

# 全部测试 + 覆盖率
make test
```

### 代码格式化

```bash
# 格式化
ruff format src/python/

# Linting
ruff check src/python/ --fix
```

---

## 实验数据

所有实验数据已整理到 `data/` 目录下，按照 **模型 × 基准测试** 的组合组织。详见 [`data/README.md`](data/README.md)。

### 已完成的实验

| 实验 | 模型 | 基准测试 | 状态 | 论文可用 |
|------|------|---------|------|---------|
| `exp-glm5-skillsbench` | GLM-5.1 | SkillsBench | ✅ 320/320 | ✅ 主实验 |
| `exp-deepseek_v4_flash-skillsbench` | deepseek-v4-flash | SkillsBench | ✅ 320/320 | ✅ 跨模型对比 |
| `exp-deepseek_v4_pro-skillsbench` | deepseek-v4-pro | SkillsBench | ✅ 320/320 | ✅ 跨模型对比 |
| `exp-qwen3_coder_flash-skillsbench` | qwen3-coder-flash | SkillsBench | ⚠️ 154/320 | ❌ 未完成 |
| `exp-glm5-swebench_v5` | GLM-5.1 | SWE-bench V5 | ⚠️ 部分完成 | ✅ 辅助对比 |
| `exp-deepseek_v4_flash-swebench_v5` | deepseek-v4-flash | SWE-bench V5 | ✅ 320/320 | ✅ SWE-bench 主实验 |
| `exp-glm5-swebench_planb` | GLM-5.1 | SWE-bench Plan B | ⚠️ Predict only | ❌ 评估不完整 |
| `exp-graphskill-performance` | — | 系统性能 | ✅ 5 组基准测试 | ✅ 系统性能 |

### 论文数据使用指南

**可用于论文的实验（6 组）**：

| 实验 | 用途 | 关键数据 |
|------|------|---------|
| GLM-5.1 × SkillsBench | **主实验** | GS wins=3, violations=0, 8 张图表 |
| deepseek-v4-flash × SkillsBench | 跨模型对比 | GS wins=1, violations=1 |
| deepseek-v4-pro × SkillsBench | 跨模型对比 | GS wins=1, violations=0 |
| deepseek-v4-flash × SWE-bench V5 | **SWE-bench 主实验** | GS ≥ ZS 反转, 消融实验 |
| GLM-5.1 × SWE-bench V5 | 辅助对比 | 50 样本（注意 CUDA 问题） |
| GraphSkill 系统性能 | **系统性能** | 延迟 ~23ms, QPS ~44, Token ~715, 消融验证 |

**不可用于论文的实验（2 组）**：

| 实验 | 排除原因 |
|------|---------|
| qwen3-coder-flash × SkillsBench | 仅完成 48.1%，数据不完整 |
| GLM-5.1 × SWE-bench Plan B | 仅 predict 阶段，无通过率数据 |

### 论文数据列举建议

在论文 Experiments 章节中，建议按以下顺序组织：

1. **GLM-5.1 × SkillsBench（主实验）**：核心指标表、GS vs VR 饼图、运行时间柱状图
2. **跨模型对比（SkillsBench）**：GLM-5.1 vs deepseek-v4-flash vs deepseek-v4-pro
3. **deepseek-v4-flash × SWE-bench V5（SWE-bench 主实验）**：核心指标表、消融分析
4. **辅助分析**：GLM-5.1 × SWE-bench V5（50 样本）
5. **系统性能实验**：路由延迟分解、Token 消耗、消融验证、构建开销、缓存效果

### 关键实验发现

- **GLM-5.1 × SkillsBench**：GS wins=3, violations=0，验证了 VR-First 架构的 GS ≥ VR 保证
- **DeepSeek 模型**：在 SkillsBench 上表现不佳（极低奖励），但在 SWE-bench V5 上 GS ≥ ZS
- **消融实验**：VR + Expansion + MWIS（完整 GS）效果最优

---

## 论文撰写

论文 LaTeX 源码位于 `paper/mypaper/`，Markdown 草稿位于 `paper/md-draft/`。详见 [`plans/PAPER_WRITING_PLAN.md`](plans/PAPER_WRITING_PLAN.md)。

### 论文结构

| 章节 | 文件 | 状态 |
|------|------|------|
| Abstract | `sections/Abstract.tex` | 草稿 |
| Introduction | `sections/Introduction.tex` | 草稿 |
| Background | `sections/Background.tex` | 待编写 |
| Design | `sections/Design.tex` | 待编写 |
| Experiments | `sections/Experiments.tex` | 待编写 |
| Discussion | `sections/Discussion.tex` | 待编写 |

---

## 开发规范

### Git 提交规范

严格遵循 Conventional Commits 规范（英文）：

```
:<gitmoji>: <type>(<scope>): <subject>
```

示例：`feat(routing): add VR-First enhancement score computation`

### 编码规范

- **Python**: PEP 8，使用 ruff 格式化和 linting
- **Type Hints**: 所有 Python 代码必须包含类型注解
- **Early Return**: 优先使用提前返回减少嵌套
- **Modularity**: 单个函数不超过 50 行，保持单一职责
- **Error Handling**: 不静默吞咽错误，必须正确抛出或返回标准化错误对象

### 测试要求

- 核心逻辑必须有测试覆盖
- 使用 pytest 框架
- 集成测试需要真实的数据库连接

---

## 技术栈

| 组件 | 技术选型 | 用途 |
|------|---------|------|
| 图数据库 | Neo4j 5.x | 技能图谱存储（REQUIRES/CONFLICTS_WITH/ENHANCES/SUBSTITUTES 边） |
| 向量数据库 | Milvus 2.4+ | 语义向量检索（VR Baseline） |
| 缓存 | Redis 7.x | 路由结果缓存 |
| 嵌入模型 | Sentence Transformers | 技能嵌入生成 |
| LLM API | GLM-5.1 / deepseek-v4 | 实验用语言模型 |
| 实验框架 | Harbor (OpenHands SDK) | Docker 容器化任务执行 |
| 测试框架 | pytest | 单元/集成/E2E 测试 |
| 代码质量 | ruff | 格式化和 linting |

---

## 许可证

Apache License 2.0

---

## 联系方式

- **项目作者**: Owen (GraphSkill Architecture Team)
- **项目状态**: 研究与开发阶段
- **创建日期**: 2026-04-12
