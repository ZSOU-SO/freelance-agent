# freelance-agent

`freelance-agent` 是一个面向自由职业者和外包团队的全栈需求分析助手。用户输入客户的原始需求后，系统会提取项目范围、识别交付风险、按照本地规则计算报价和工期，并生成接单建议、技术方案、追问问题及可直接发送给客户的回复。

第一阶段 MVP 支持 OpenAI Agents SDK 与完全离线的本地规则双模式。没有配置 API Key 时，应用仍能正常启动并完成整条分析流程。

## 核心功能

- 从自然语言中提取项目类型、功能、客户预算和目标工期；
- 识别支付、硬件、第三方平台和紧急交付风险；
- 使用 `backend/pricing_rules.json` 计算人民币税前报价区间；
- 输出是否建议接单、技术方案、报价、工期、追问问题和客户回复；
- 逐步骤记录执行模式、耗时、降级状态和错误信息；
- 将每次完整分析保存到 SQLite，并在前端展示历史记录；
- 无 `OPENAI_API_KEY` 时自动使用本地规则完成全部分析。

## Agent 流水线架构

Pipeline Orchestrator 始终按固定顺序编排四个步骤：

```text
客户需求文本
    │
    ▼
RequirementAgent  ── 提取类型、功能、预算、工期及缺失信息
    │ Pydantic 校验
    ▼
TechnicalAgent    ── 生成技术方案、工期、风险及接单建议
    │ Pydantic 校验
    ▼
QuoteAgent        ── 强制调用本地报价工具，模型只解释报价
    │ Pydantic 校验
    ▼
ReplyAgent        ── 生成追问问题、建议摘要和客户回复
    │
    ▼
Pipeline Orchestrator 统一响应 ──► SQLite
```

每个 Agent 使用独立的 Pydantic 输入、输出模型。前一步输出只有通过校验后才能进入下一步，四个 Agent 不直接构造最终 API 响应。

`QuoteAgent` 必须调用本地 `calculate_quote` 工具。最终报价始终以 `backend/pricing_rules.json` 的计算结果为准，大模型只能补充报价解释、假设和付款建议，不能修改金额区间。

第一阶段没有 Manager Agent 和 handoff；执行器接口与编排层已保持独立，便于后续扩展。

## 本地降级机制

系统提供两级降级：

1. **无 Key 的完整本地模式**：`OPENAI_API_KEY` 未设置或为空时，四个步骤都调用对应的本地执行器，不创建 OpenAI 客户端。响应标记为 `analysis_mode: local_fallback`，前端显示“本地规则分析，未调用大模型”。这是正常运行模式，因此 `fallback_occurred` 为 `false`。
2. **Agent 单步故障降级**：配置 Key 后，流水线优先使用四个 Agent。任一步骤发生超时、调用失败或输出校验失败时，Orchestrator 会记录经过脱敏的错误并仅对该步骤调用本地执行器，其余步骤继续执行。此时整体 `analysis_mode` 仍为 `agents`，`fallback_occurred` 为 `true`。

两种模式使用完全相同的 `AnalysisResponse` 数据结构，前端、存储层和测试无需针对模式维护两套契约。

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 后端 | Python 3.11+、FastAPI、Pydantic v2、Uvicorn |
| Agent | OpenAI Agents SDK、四 Agent 显式流水线 |
| 本地分析 | Python 规则执行器、正则与关键词规则 |
| 报价 | 本地 `pricing_rules.json` 与受控报价工具 |
| 数据库 | SQLite |
| 前端 | Vue 3、TypeScript、Vite |
| 测试 | pytest、pytest-asyncio、Vitest、Vue Test Utils |

## 项目目录

```text
freelance-agent/
├─ backend/
│  ├─ app/
│  │  ├─ agents/          # 四个 OpenAI Agent 工厂
│  │  ├─ executors/       # Agent 适配器和四个本地执行器
│  │  ├─ pipeline/        # 固定顺序、校验、降级和遥测
│  │  ├─ services/        # 报价、风险和工期规则
│  │  ├─ persistence/     # SQLite 数据库与 repository
│  │  ├─ api/             # FastAPI 路由与依赖
│  │  ├─ schemas/         # 统一 Pydantic 数据契约
│  │  └─ main.py          # FastAPI 应用工厂
│  ├─ tests/              # 后端单元与集成测试
│  ├─ pricing_rules.json  # 报价金额的唯一规则来源
│  └─ pyproject.toml
├─ frontend/
│  ├─ src/
│  │  ├─ api/             # 后端 API 客户端
│  │  ├─ components/      # 表单、结果、历史和遥测组件
│  │  ├─ composables/     # 分析状态管理
│  │  ├─ tests/           # 前端组件测试
│  │  └─ types/           # 统一响应 TypeScript 类型
│  ├─ package.json
│  └─ vite.config.ts
├─ docs/superpowers/      # 设计与实施计划
├─ .env.example           # 后端环境变量示例，不含密钥
└─ README.md
```

## 环境要求

- Python 3.11 或更高版本；
- Node.js 20 或更高版本；
- npm 10 或更高版本。

所有命令默认从仓库根目录执行。

## 后端启动方法

### Windows PowerShell

```powershell
python -m venv .venv
& ".\.venv\Scripts\python.exe" -m pip install -e ".\backend[dev]"

# 留空表示使用完整本地降级模式
$env:OPENAI_API_KEY = ""

& ".\.venv\Scripts\python.exe" -m uvicorn backend.app.main:create_app --factory --reload
```

### macOS / Linux

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e './backend[dev]'
export OPENAI_API_KEY=''
.venv/bin/python -m uvicorn backend.app.main:create_app --factory --reload
```

- 后端默认地址：<http://127.0.0.1:8000>
- OpenAPI 文档：<http://127.0.0.1:8000/docs>

## 前端启动方法

打开另一个终端并在仓库根目录执行：

```powershell
npm.cmd --prefix frontend install
npm.cmd --prefix frontend run dev
```

前端默认地址：<http://localhost:5173>。Vite 开发服务器会将 `/api` 代理到 `http://127.0.0.1:8000`。

## 环境变量说明

| 变量 | 必需 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `OPENAI_API_KEY` | 否 | 空 | 非空时启用 Agents 模式；为空时使用完整本地模式 |
| `OPENAI_MODEL` | 否 | Agents SDK 默认模型 | 可选的 Agent 模型名 |
| `DATABASE_PATH` | 否 | `backend/data/freelance_agent.sqlite3` | SQLite 文件位置 |
| `PRICING_RULES_PATH` | 否 | `backend/pricing_rules.json` | 本地报价规则位置 |
| `FRONTEND_ORIGIN` | 否 | `http://localhost:5173` | 后端允许的前端来源 |
| `VITE_API_BASE_URL` | 否 | `/api/v1` | 前端 API 基础地址 |

根目录 `.env.example` 和 `frontend/.env.example` 只提供变量名称与非敏感默认值。当前后端直接读取进程环境变量，不会自动加载 `.env`；本地启动请像上面的命令一样在当前终端设置变量，生产环境应使用部署平台的密钥管理功能。

不要把真实 API Key 写入 README、代码、提交信息或 `.env.example`。`.env`、`.env.*`、数据库文件、依赖目录、缓存和构建产物均已加入 `.gitignore`。

## API

| 方法 | 路径 | 说明 |
| --- | --- | --- |
| `POST` | `/api/v1/analyses` | 执行并保存一次分析 |
| `GET` | `/api/v1/analyses` | 分页读取历史记录 |
| `GET` | `/api/v1/analyses/{id}` | 读取一条完整记录 |
| `GET` | `/api/v1/health` | 查看服务状态和默认分析模式 |

## 测试命令

后端测试强制清空 Key，不会调用真实 OpenAI API：

```powershell
$env:OPENAI_API_KEY = ""
& ".\.venv\Scripts\python.exe" -m pytest backend/tests -ra
```

前端组件测试和生产构建：

```powershell
npm.cmd --prefix frontend test -- --run
npm.cmd --prefix frontend run build
```

测试覆盖四个 Agent 适配器、四个本地执行器、报价工具、风险与工期规则、完整流水线、SQLite repository、FastAPI 接口和主要 Vue 组件。Agent 单元测试通过注入 runner 完成，不调用真实服务。

## 示例输入与输出

输入：

```text
开发一个带微信支付和订单管理的小程序，预算3万元，希望四周上线，需要连接第三方物流平台。
```

本地模式的响应结构示例（ID、时间、金额和耗时会随实际运行及规则变化）：

```json
{
  "id": "example-analysis-id",
  "created_at": "2026-07-20T12:00:00Z",
  "requirement_text": "开发一个带微信支付和订单管理的小程序，预算3万元，希望四周上线，需要连接第三方物流平台。",
  "analysis_mode": "local_fallback",
  "fallback_occurred": false,
  "requirement": {
    "project_type": "mini_program",
    "features": ["payment", "third_party_integration"],
    "client_budget": {
      "min_amount": 27000,
      "max_amount": 30000,
      "currency": "CNY",
      "raw_text": "预算3万元"
    },
    "desired_deadline": {
      "min_days": 20,
      "max_days": 20,
      "explanation": "客户明确的目标交付时间",
      "raw_text": "四周上线"
    },
    "risk_signals": ["third_party_platform"],
    "missing_information": ["请确认部署环境及验收标准。"]
  },
  "quote": {
    "pricing": {
      "min_amount": 23000,
      "max_amount": 45000,
      "currency": "CNY",
      "calculation_items": [
        {
          "code": "base:mini_program",
          "label": "微信小程序",
          "kind": "base",
          "min_amount": 15000,
          "max_amount": 28000,
          "multiplier": null
        },
        {
          "code": "feature:payment",
          "label": "支付功能",
          "kind": "addition",
          "min_amount": 4000,
          "max_amount": 6000,
          "multiplier": null
        },
        {
          "code": "feature:third_party_integration",
          "label": "第三方平台集成",
          "kind": "addition",
          "min_amount": 3000,
          "max_amount": 7000,
          "multiplier": null
        },
        {
          "code": "risk:third_party_platform",
          "label": "第三方平台风险预留",
          "kind": "addition",
          "min_amount": 1000,
          "max_amount": 4000,
          "multiplier": null
        }
      ]
    },
    "explanation": "报价由本地规则计算，最终金额以 pricing_rules.json 为准。",
    "assumptions": [],
    "payment_terms": "建议按里程碑分阶段付款。"
  },
  "recommendation": {
    "should_accept": true,
    "verdict": "conditional",
    "reasons": ["项目可实现，但需先确认风险边界和里程碑"]
  },
  "follow_up_questions": ["请确认部署环境及验收标准。"],
  "client_reply": "您好，感谢您提供项目需求。预计工期和报价已按本地规则生成，确认补充问题后可以进一步细化范围和里程碑。",
  "telemetry": {
    "total_duration_ms": 5.2,
    "steps": [
      {
        "step": "requirement",
        "execution_mode": "local_fallback",
        "duration_ms": 0.8,
        "fallback_used": false,
        "error": null
      }
    ]
  }
}
```

实际响应还会包含完整的 `technical_solution`、`estimated_duration`、`risks` 以及四个步骤的遥测记录。统一契约以 FastAPI 的 `/docs` 页面为准。

## 报价规则

`backend/pricing_rules.json` 是报价金额的唯一来源，计算顺序为：

1. 项目类型基础价；
2. 功能加价；
3. 风险固定预留；
4. 支付高风险或紧急交付系数；
5. 按 `rounding_unit` 向外取整。

第三方平台费用、硬件采购费和税费不包含在开发报价中。修改规则后必须重新运行报价工具与完整流水线测试。

## 当前限制

- 本地需求提取依赖关键词和正则表达式，对复杂或含糊需求的理解有限；
- 第一阶段没有登录、权限和多租户隔离；
- SQLite 适合单机和小规模使用，不适合高并发部署；
- 未实现 Manager Agent、handoff、流式输出或队列任务；
- Agents 模式会产生 OpenAI API 调用费用，本地模式不会调用大模型。

## 后续规划

以下内容仅作为未来方向，尚未进入开发：

- 增加登录、权限和多租户数据隔离；
- 增加可视化报价规则管理和版本审计；
- 增加 Manager Agent、handoff 或可配置编排策略；
- 增加流式进度、后台任务与失败重试；
- 将生产数据库迁移到 PostgreSQL，并补充部署与监控方案；
- 增加真实 Agents 模式的受控端到端验收流程。

## License

当前仓库尚未添加开源许可证。对外公开前请根据实际用途选择许可证。
