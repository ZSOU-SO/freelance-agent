# Freelance Agent Phase 2A：历史案例 RAG 设计

## 1. 文档状态

- 阶段：Phase 2A，仅设计，不包含实现。
- 日期：2026-07-21。
- 目标项目：`C:\Users\1\Documents\Codex\freelance-agent`。
- 前置版本：Phase 1 四 Agent 显式流水线 MVP。
- 本文采用保守假设直接完成设计；需要产品确认的事项统一列在文末，不阻塞今晚的文档工作。

## 2. 目标

在分析新的外包需求时，系统先完成 RequirementAgent，再从本地历史案例库中检索相似项目，将案例的功能、报价、工期、风险、成交结果和经验总结作为结构化参考，提供给 TechnicalAgent 与 QuoteAgent。最终分析结果必须清晰展示匹配案例、相似度、使用案例的 Agent，以及案例对本次分析产生的具体影响。

Phase 2A 必须在没有 `OPENAI_API_KEY` 时完整可用；本地检索不调用模型、不调用 Embedding API、不依赖外部向量数据库。`backend/pricing_rules.json` 继续是最终报价金额的唯一权威来源，历史价格只能解释或校准认知，绝不能覆盖规则报价。

## 3. 已检查的 Phase 1 基线

### 3.1 当前后端

- `PipelineOrchestrator` 以 Python 固定执行 `RequirementAgent -> TechnicalAgent -> QuoteAgent -> ReplyAgent`。
- 每一步有独立 Pydantic 输入与输出，输出再次校验后才传给下一步。
- 无 Key 时四步使用本地执行器；单个 Agent 失败时仅该步骤回退到本地执行器。
- `QuoteAgentExecutor` 强制调用本地 `calculate_quote` 工具，并使用工具产生的 `PricingCalculation` 覆盖模型金额。
- `AnalysisRepository` 把完整 `AnalysisResponse` 作为 JSON 存入 SQLite `analyses` 表。
- 当前数据库初始化只有幂等 `CREATE TABLE IF NOT EXISTS`，没有版本化迁移框架。
- 当前公开响应包含四步遥测；`ExecutionMode` 只有 `agent` 和 `local_fallback`。

### 3.2 当前前端

- Vue 3 + TypeScript 单页应用，没有 Vue Router。
- `App.vue` 同时承载分析表单、结果与历史分析记录。
- `AnalysisResult.vue` 展示报价、工期、风险、技术方案、追问和回复。
- TypeScript 手工维护与 `AnalysisResponse` 对应的统一类型。

### 3.3 必须保留的 Phase 1 不变量

1. 无 Key 可启动、可分析、可保存记录。
2. 单个 Agent 失败不终止整条流水线。
3. `pricing_rules.json` 决定报价金额和币种。
4. Pipeline Orchestrator 是最终响应的唯一汇总者。
5. 历史分析记录仍可从 SQLite 正常读取。
6. Phase 2A 不引入 Manager Agent 或 handoff。

## 4. 实现方案比较

### 4.1 方案 A：关键词与 Jaccard 加权

做法：将项目类型、功能、风险和文本关键词转为集合，按字段权重计算 Jaccard/重叠比例。

优点：

- 纯 Python、零新增运行依赖；
- 实现和调试最简单；
- 每一分都容易解释；
- 对结构化功能与风险字段效果稳定。

缺点：

- 长需求文本排序能力弱；
- 同一关键词重复出现不能自然反映重要度；
- 罕见但区分度高的词与常见词权重相同；
- 中文同义表达和词序变化容易降低召回。

### 4.2 方案 B：纯 Python BM25 + 中文字符二元组 + 结构化字段加权（推荐）

做法：原始需求和经验总结使用 BM25；中文连续文本生成字符二元组，英文、数字和技术符号生成词元；项目类型、核心功能和风险使用精确或 Jaccard 分数。最后把各项归一化并加权为 `[0, 1]` 相似度。

优点：

- 不需要 API Key、模型、向量数据库或大型依赖；
- 比纯关键词更能区分常见词和稀有词；
- 中文无需额外分词器即可获得可接受的第一版召回；
- 结构化字段权重明确，结果可解释、可稳定测试；
- Provider 边界清晰，未来可替换为 Embedding 检索。

缺点：

- 不理解真正的语义同义关系；
- 查询时需要读取候选案例并计算语料统计；
- 第一版适合小型本地案例库，不适合数十万条案例；
- 需要自行维护词元化、归一化和排序规则。

### 4.3 方案 C：SQLite FTS5/BM25

做法：为历史案例建立 FTS5 虚拟表，使用 SQLite 自带 `bm25()` 排序。

优点：

- 查询和索引都在数据库内完成；
- 数据量增长后性能优于逐次 Python 扫描；
- 不需要外部服务。

缺点：

- 默认 tokenizer 对中文不理想，若依赖 ICU/自定义 tokenizer 会出现平台差异；
- Python 自带 SQLite 是否启用相同期望扩展需要额外兼容验证；
- 索引表、触发器和迁移提高第一版复杂度；
- 检索逻辑更紧密绑定 SQLite，不利于未来 Provider 替换。

### 4.4 推荐结论

Phase 2A 采用方案 B。目标规模保守限定为单实例、最多约 2,000 条历史案例；每次查询从 repository 读取轻量搜索文档并计算分数，不引入缓存失效和多进程一致性问题。达到规模上限或通过真实案例评估证明 BM25 不足后，再实现 Embedding Provider 或 FTS5 Provider。

## 5. 总体架构

```text
客户需求
  │
  ▼
RequirementAgent / LocalRequirementExecutor
  │ 已验证 RequirementAgentOutput
  ▼
CaseSearchService
  ├─ CaseRepository ── SQLite historical_cases
  └─ CaseRetrievalProvider
       └─ LocalBm25CaseRetrievalProvider（Phase 2A 默认）
  │ CaseRetrievalResult + CaseInsight
  ▼
TechnicalAgent / LocalTechnicalExecutor
  │ 技术方案、风险、工期、案例影响
  ▼
QuoteAgent / LocalQuoteExecutor
  ├─ 相似案例只用于解释和对比
  └─ PricingService / pricing_rules.json 锁定金额
  │
  ▼
ReplyAgent / LocalReplyExecutor
  │
  ▼
Pipeline Orchestrator
  ├─ 汇总 case_rag、五步遥测和统一响应
  └─ AnalysisRepository 保存完整 JSON
```

检索由 Python Orchestrator 主动执行，不作为模型自主决定是否调用的工具。这样无 Key 路径与 Agent 路径共享同一个检索结果，顺序固定，可测试，也不会因模型跳过工具而失去案例上下文。

OpenAI Agents SDK 的本地 run context 是代码依赖注入容器，并不会自动呈现给模型；模型要使用新数据，必须把数据放入 Agent 的输入、动态 instructions 或可调用工具。Phase 2A 选择把经过裁剪的案例引用加入 `TechnicalAgentInput` 和 `QuoteAgentInput`，继续沿用当前执行器序列化 Pydantic 输入的模式：[Agents 与结构化输出](https://openai.github.io/openai-agents-python/agents/)、[Context management](https://openai.github.io/openai-agents-python/context/)。

## 6. 历史案例领域模型

### 6.1 Pydantic 模型

新增 `backend/app/schemas/case.py`，核心公开模型为 `HistoricalCase`：

| 字段 | 类型 | 必需 | 规则 |
| --- | --- | --- | --- |
| `id` | `str` | 服务端生成 | UUID 字符串，内部主键 |
| `project_number` | `str` | 是 | 3～64 字符，ASCII 字母、数字、`.`、`_`、`-`；不区分大小写唯一 |
| `project_type` | `str` | 是 | 与 RequirementAgent 的标准项目类型一致，未知类型允许 `other` |
| `original_requirement` | `str` | 是 | 1～20,000 字符，保存客户原始需求 |
| `core_features` | `list[str]` | 是 | 至少 1 项，去空白、去重并保留顺序 |
| `client_budget` | `MoneyRange \| None` | 否 | CNY 整数元，未知时为 `null` |
| `suggested_quote` | `MoneyRange` | 是 | 当时建议报价，CNY 税前区间 |
| `final_deal_price` | `int \| None` | 条件必需 | 成交时必填且非负；未成交时必须为 `null` |
| `estimated_duration` | `DurationRange` | 是 | 当时预计工作日区间 |
| `actual_duration_days` | `int \| None` | 否 | 正整数工作日；未成交时必须为 `null` |
| `risks` | `list[RiskItem]` | 是 | 可为空；复用 Phase 1 风险枚举和结构 |
| `is_won` | `bool` | 是 | 是否最终成交 |
| `lessons_learned` | `str` | 是 | 1～5,000 字符的经验总结 |
| `created_at` | `datetime` | 服务端生成 | UTC 时间 |
| `updated_at` | `datetime` | 服务端生成 | 每次编辑更新，UTC 时间 |

`MoneyRange` 使用 `min_amount`、`max_amount`、固定 `currency: CNY`，并验证 `min_amount <= max_amount`。`DurationRange` 使用正整数 `min_days`、`max_days` 并验证范围。金额单位与 Phase 1 一致，使用人民币“元”的整数，不使用浮点数。

API 写入模型：

- `HistoricalCaseCreate`：包含所有用户可编辑字段，不包含 `id/created_at/updated_at`。
- `HistoricalCaseUpdate`：采用完整替换语义，与 Create 字段相同。
- `HistoricalCaseSummary`：列表和检索使用的裁剪模型。
- `HistoricalCaseListResponse`：`items/total/limit/offset`。

使用 `PUT` 而不是部分 `PATCH`，避免 `is_won`、`final_deal_price` 和 `actual_duration_days` 的跨字段状态在部分更新中产生歧义。

### 6.2 SQLite 表

新增 `historical_cases`：

```sql
CREATE TABLE historical_cases (
    id TEXT PRIMARY KEY,
    project_number TEXT NOT NULL COLLATE NOCASE UNIQUE,
    project_type TEXT NOT NULL,
    original_requirement TEXT NOT NULL,
    core_features_json TEXT NOT NULL,
    client_budget_json TEXT,
    suggested_quote_json TEXT NOT NULL,
    final_deal_price INTEGER,
    estimated_duration_json TEXT NOT NULL,
    actual_duration_days INTEGER,
    risks_json TEXT NOT NULL,
    is_won INTEGER NOT NULL CHECK (is_won IN (0, 1)),
    lessons_learned TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    CHECK (final_deal_price IS NULL OR final_deal_price >= 0),
    CHECK (actual_duration_days IS NULL OR actual_duration_days > 0)
);

CREATE INDEX idx_historical_cases_project_type
    ON historical_cases(project_type);
CREATE INDEX idx_historical_cases_is_won
    ON historical_cases(is_won);
CREATE INDEX idx_historical_cases_created_at
    ON historical_cases(created_at DESC);
```

列表字段以列保存，复合值使用 Pydantic JSON，延续 Phase 1 的简单 SQLite 策略。所有读取必须重新经过 Pydantic 校验，所有 SQL 必须参数化。

### 6.3 迁移策略

新增 `backend/app/persistence/migrations.py`：

- 创建 `schema_migrations(version TEXT PRIMARY KEY, applied_at TEXT NOT NULL)`；
- 迁移名使用固定字符串 `20260721_01_historical_cases`；
- 每个迁移在单个事务中执行；成功后记录版本，重复启动不重复执行；
- 迁移失败自动回滚，不留下半张表或半个索引；
- 现有 `analyses` 表初始化保持独立，避免 Phase 2A 迁移影响 Phase 1 数据。

案例迁移失败时，应用仍启动并保留 Phase 1 分析能力。`CaseSubsystem` 标记为 unavailable：案例 CRUD/Search 返回 503；流水线把 `case_rag.status` 设为 `failed`、记录脱敏错误并继续 Technical/Quote/Reply；健康检查返回 `status: degraded` 和 `case_rag: unavailable`。若 Phase 1 自身的 `analyses` 初始化失败，仍按当前策略视为核心启动错误。

## 7. CRUD 与检索 API

所有路由位于 `/api/v1/cases`，静态 `/search` 路由必须在 `/{case_id}` 之前注册。

### 7.1 CRUD

| 方法 | 路径 | 响应 | 说明 |
| --- | --- | --- | --- |
| `POST` | `/api/v1/cases` | 201 `HistoricalCase` | 新增案例 |
| `GET` | `/api/v1/cases` | 200 `HistoricalCaseListResponse` | 按创建时间倒序分页；可选 `project_type`、`is_won`、`q` |
| `GET` | `/api/v1/cases/{case_id}` | 200 `HistoricalCase` | 案例详情 |
| `PUT` | `/api/v1/cases/{case_id}` | 200 `HistoricalCase` | 完整编辑，保留 `id/created_at` 并更新 `updated_at` |
| `DELETE` | `/api/v1/cases/{case_id}` | 204 | 硬删除 |

错误映射：

- Pydantic 格式错误：422；
- 项目编号重复：409，错误码 `case_project_number_conflict`；
- 案例不存在：404；
- 案例子系统不可用：503；
- 持久化 JSON 损坏：记录案例 ID，返回不含原始数据的 500。

Phase 2A 不实现软删除和审计日志；前端删除前必须二次确认。

### 7.2 相似案例检索

`POST /api/v1/cases/search`

请求 `CaseSearchRequest`：

```json
{
  "requirement_text": "开发带微信支付和订单管理的小程序",
  "project_type": "mini_program",
  "core_features": ["payment", "third_party_integration"],
  "risk_categories": ["third_party_platform"],
  "top_k": 5,
  "min_similarity": 0.25
}
```

只有 `requirement_text` 必填；公开 API 可省略结构化提示。流水线调用时必须把 RequirementAgent 的项目类型、功能和风险一起传入。

响应复用统一的 `CaseRagResult`；公开搜索没有 Agent 消费者，因此 `used_by_agents` 和 `impact_summary` 为空：

```json
{
  "status": "matched",
  "retrieval_mode": "local_bm25",
  "min_similarity": 0.25,
  "used_by_agents": [],
  "impact_summary": [],
  "matches": [
    {
      "case": {"id": "...", "project_number": "FA-2026-001"},
      "similarity": 0.7821,
      "matched_signals": ["project_type", "feature:payment", "text:微信支付"]
    }
  ]
}
```

公开 Search API 的 `empty_library` 和 `no_match` 返回 200；真正的检索/存储失败返回 503，响应体仍使用 `CaseRagResult` 并令 `status=failed`。`top_k` 范围 1～10，默认 5；`min_similarity` 范围 0～1，默认 0.25。

## 8. 本地检索算法

### 8.1 词元化

`CaseTokenizer` 执行：

1. Unicode NFKC 归一化并转小写；
2. 英文、数字及常见技术符号按 `[a-z0-9_+#.-]+` 提取；
3. 中文连续片段生成字符二元组；长度为 1 时保留单字；
4. 去除有限、版本化的中英文停用词；
5. 不读取或调用外部分词模型。

示例：`微信支付 API` 产生 `微信`、`信支`、`支付`、`api`。

### 8.2 BM25 和结构化得分

文本语料由 `original_requirement + lessons_learned` 组成，使用标准 BM25，固定参数 `k1=1.5`、`b=0.75`。原始 BM25 通过 `bm25 / (bm25 + 1)` 映射到 `[0, 1)`。

结构化得分：

- `feature_score`：查询功能与案例功能的 Jaccard；
- `project_type_score`：类型完全相同为 1，否则 0；
- `risk_score`：风险类别 Jaccard；双方均为空时为 0，避免“都没有信息”形成虚高相似度。

最终相似度：

```text
similarity =
    0.45 * text_score
  + 0.30 * feature_score
  + 0.15 * project_type_score
  + 0.10 * risk_score
```

成交与否、成交价和创建时间不参与相似度，避免“高价/成交案例天然更相似”的偏差；它们只在匹配后作为参考证据。

排序规则：

1. `similarity` 降序；
2. `feature_score` 降序；
3. `created_at` 降序；
4. `project_number` 升序，保证完全确定的并列顺序。

排名计算保留完整浮点精度，API 展示四位小数。低于阈值的案例不传给 Agent。

### 8.3 Provider 接口

```python
class CaseRetrievalProvider(Protocol):
    name: str

    async def rank(
        self,
        query: CaseSearchQuery,
        candidates: list[CaseSearchDocument],
    ) -> list[ScoredCase]: ...


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
```

`CaseSearchService` 负责从 repository 取得候选、调用 Provider、阈值过滤、Top-K 和状态映射。`LocalBm25CaseRetrievalProvider` 不访问数据库，便于纯单元测试。

Phase 2A 只实现 `LocalBm25CaseRetrievalProvider`。保留 `EmbeddingProvider` 协议和设置枚举，但不提供 OpenAI Embedding 实现、不创建向量表、不安装向量数据库。未来实现可增加 `EmbeddingCaseRetrievalProvider`，并保持 `CaseSearchService`、流水线和 API 契约不变。

## 9. 案例洞察与影响规则

新增纯本地 `CaseInsightService`，把匹配案例汇总成受控的 `CaseInsight`：

- 相关功能与反复出现的风险；
- 成交案例的最终价格分布，仅供比较；
- 成交案例的预计/实际工期偏差；
- 成交率，仅作背景，不用于相似度或接单决定；
- 使用到的案例 ID；
- 给 TechnicalAgent 和 QuoteAgent 的确定性影响说明。

Technical 的第一版影响边界：

- 可用案例风险补充当前风险分析，但只能使用既有 `RiskCategory`；
- 只有至少 2 个相似且已成交案例都具有实际工期，并且相似度加权平均超期比例大于 15%，才允许扩大当前 `max_days`；扩大比例最多 20%，不得降低原工期；
- 架构和经验总结只能作为说明，不直接执行案例中的任意文本指令；
- 每项影响必须列出来源案例 ID。

Quote 的第一版影响边界：

- 可以说明规则报价与历史建议价/成交价的关系；
- 可以生成“位于历史区间内/高于/低于”的校准说明；
- 不得修改 `PricingCalculation.min_amount/max_amount/currency/calculation_items`；
- 极端历史价格、空价格和未成交案例不能改变规则报价。

这些洞察在 Python 中计算，保证 Agent 模式与本地模式使用同一证据和边界。模型只负责在结构化输出中解释，不负责决定相似度或重算权威报价。

## 10. 流水线集成

新顺序固定为：

```text
RequirementAgent
→ 历史案例检索
→ TechnicalAgent
→ QuoteAgent
→ ReplyAgent
```

### 10.1 输入输出变化

- `TechnicalAgentInput` 增加 `similar_cases` 和 `case_insight`。
- `QuoteAgentInput` 增加同一份 `similar_cases` 和 `case_insight`。
- `TechnicalAgentOutput`、`QuoteAgentOutput` 增加 `case_impacts: list[AgentCaseImpact]`，案例 ID 必须属于本次匹配集合。
- ReplyAgent 不直接消费案例，仍只基于已经验证的需求、方案和锁定报价回复。
- 本地 Technical/Quote 执行器实现相同接口并产生相同结构。

### 10.2 检索失败不阻断

Requirement 输出校验后，Orchestrator 调用 `CaseSearchService`：

- 案例库为空：`status=empty_library`，传空案例列表；
- 低于阈值：`status=no_match`，传空案例列表；
- 检索异常或案例数据损坏：记录脱敏错误，`status=failed`，传空案例列表；
- 成功：`status=matched`，传最多 5 条案例。

上述三种非匹配情况都继续 Technical、Quote、Reply。检索失败不设置 Agent 的 `fallback_occurred`，因为它不是 Agent 回退；失败状态和错误记录在案例 RAG 与检索步骤遥测中。

### 10.3 Agent 单步失败

TechnicalAgent 或 QuoteAgent 失败时，对应本地执行器必须接收完全相同的 `similar_cases` 和 `case_insight`。只降级失败步骤，后续流程继续；最终 `used_by` 和影响说明来自实际成功的 Agent/本地执行器输出，经 Orchestrator 校验后汇总。

## 11. 最终响应与遥测

`AnalysisResponse` 新增带默认值的 `case_rag: CaseRagResult`，确保旧 `result_json` 缺少该字段时仍能读取并得到 `status=not_run`。

```json
{
  "case_rag": {
    "status": "matched",
    "retrieval_mode": "local_bm25",
    "min_similarity": 0.25,
    "used_by_agents": ["TechnicalAgent", "QuoteAgent"],
    "impact_summary": [
      "TechnicalAgent 参考 2 个已成交案例校准最大工期",
      "QuoteAgent 仅使用案例解释价格差异，未修改规则报价"
    ],
    "matches": [
      {
        "case": {"id": "...", "project_number": "FA-2026-001"},
        "similarity": 0.7821,
        "matched_signals": ["project_type", "feature:payment"],
        "used_by": ["TechnicalAgent", "QuoteAgent"],
        "impacts": [
          {
            "agent": "TechnicalAgent",
            "summary": "参考实际工期超期记录，将最大工期增加 10%"
          },
          {
            "agent": "QuoteAgent",
            "summary": "用于解释历史成交价差异；规则报价未改变"
          }
        ]
      }
    ],
    "warning": null
  }
}
```

`CaseRagStatus`：`not_run | matched | empty_library | no_match | failed`。

`AnalysisMode` 保持 `agents | local_fallback` 不变。仅用于单步遥测的 `ExecutionMode` 增加 `local_retrieval`，并为未来预留 `embedding_retrieval`；`CaseRagResult.retrieval_mode` 则记录具体 Provider（Phase 2A 固定为 `local_bm25`）。`PipelineTelemetry.steps` 变为五步：`requirement`、`case_retrieval`、`technical`、`quote`、`reply`。案例库为空和低分匹配不是错误；检索失败才填写脱敏 `error`。

历史分析列表读取旧 JSON 时由 Pydantic 默认字段补齐 `case_rag`，无需重写旧记录。

## 12. 前端设计

引入轻量 `vue-router`，路由：

| 路径 | 页面 | 说明 |
| --- | --- | --- |
| `/` | `AnalysisView.vue` | 保留现有需求分析与历史分析记录 |
| `/cases` | `CaseListView.vue` | 案例分页、类型/成交筛选、查看、编辑、删除 |
| `/cases/new` | `CaseFormView.vue` | 新增案例 |
| `/cases/:id/edit` | `CaseFormView.vue` | 加载并完整编辑案例 |

组件与模块：

- `frontend/src/api/cases.ts`：CRUD 与 Search 请求；
- `frontend/src/types/case.ts`：案例、检索和 case_rag 类型；
- `frontend/src/composables/useCases.ts`：列表、详情、保存、删除状态；
- `CaseTable.vue`：项目编号、类型、报价、成交、时间和操作；
- `CaseForm.vue`：核心功能、预算、报价、工期、风险和经验字段；
- `CaseDetail.vue`：只读详情；
- `SimilarCasesPanel.vue`：分析结果中的相似案例卡片。

`SimilarCasesPanel` 展示：

- 案例编号和项目类型；
- 相似度百分比及匹配信号；
- 功能、客户预算、建议报价、成交价；
- 预计/实际工期、风险、成交状态；
- `TechnicalAgent`/`QuoteAgent` 使用徽标；
- 每个 Agent 的影响说明；
- `empty_library/no_match/failed` 的非阻塞提示。

表单采用整数金额和工作日，前端进行即时校验，但后端 Pydantic 始终是最终校验权威。删除必须二次确认。Phase 2A 不做批量导入、富文本编辑或复杂图表。

## 13. 异常处理

| 场景 | API 行为 | 流水线行为 | 前端行为 |
| --- | --- | --- | --- |
| 案例库为空 | Search 200 `empty_library` | 空上下文继续分析 | 显示“暂无历史案例，本次未使用案例参考” |
| 相似度过低 | Search 200 `no_match` | 空上下文继续分析 | 显示“未找到达到阈值的相似案例” |
| 检索失败 | Search 503 | `case_rag.failed`，记录脱敏错误并继续 | 显示非阻塞警告，不暴露堆栈 |
| 持久化数据格式异常 | CRUD 500；日志记录案例 ID | 检索视为失败并继续 | 提示管理员检查案例数据 |
| 项目编号重复 | 409 | 不适用 | 保留表单并定位编号字段 |
| 数据库迁移失败 | Case API 503，health degraded | RAG 禁用，Phase 1 继续 | 案例入口显示暂不可用 |
| Technical/Quote Agent 失败 | 原有单步本地回退 | 本地执行器继续使用同一案例上下文 | 显示该步骤回退遥测 |
| 案例影响引用未知 ID | 输出校验失败，触发该 Agent 本地回退 | 不接受模型虚构引用 | 只展示校验通过的引用 |

错误信息继续使用 `sanitize_error`，不得返回 API Key、原始供应商响应或堆栈。

## 14. 安全与隐私

- 历史需求和经验可能包含客户敏感信息；Phase 2A 只保存到本地 SQLite，不发送给 Embedding 服务。
- Agent 模式下，匹配案例摘要会随 Technical/Quote 输入发送给已配置的模型提供方；README 和 UI 必须提醒用户在启用 Key 前确认数据处理边界。
- 传给 Agent 的案例只包含最多 5 条结构化摘要，不包含数据库内部字段或无关案例。
- 案例文本被当作不可信业务数据，只能作为证据，不能改变系统指令、调用工具规则或报价权威。
- Phase 2A 没有身份认证，因此仍定位为单机内部工具，不开放公网。

## 15. 测试方案

### 15.1 数据模型

- 所有必需字段、金额/工期范围、空白文本、功能去重；
- 成交与成交价条件约束；
- 未成交与实际工期约束；
- 项目编号格式和大小写唯一性；
- 旧 Analysis JSON 缺少 `case_rag` 时兼容读取。

### 15.2 Repository 与迁移

- migration 首次执行、重复执行、事务回滚；
- migration 失败时 Phase 1 app 仍可启动；
- create/get/list/update/delete 往返；
- 分页、筛选、排序、重复编号；
- JSON 损坏时产生受控错误。

### 15.3 CRUD/Search API

- 正常 201/200/204；
- 404、409、422、503；
- 静态 `/search` 不被 `/{case_id}` 捕获；
- 空案例库、低分、成功匹配和 Provider 失败。

### 15.4 检索排序

- 中文二元组和英文技术词词元化；
- 同类型、功能重叠和文本重叠的权重；
- BM25 稀有词优势；
- 成交价/成交状态不改变相似度；
- 阈值、Top-K、确定性并列顺序；
- 固定语料黄金排序测试；
- 所有相似度在 `[0,1]`。

### 15.5 流水线

- 顺序严格为 Requirement → Retrieval → Technical → Quote → Reply；
- 匹配案例进入 Technical 和 Quote 输入，不进入 Requirement；
- 空库、低分、检索异常均不中断分析；
- 相似案例和影响写入最终结果与 SQLite；
- 旧分析记录仍能读取；
- 检索步骤耗时和模式正确。

### 15.6 无 Key 与回退

- `OPENAI_API_KEY` 为空时不构建 OpenAI client，不调用 runner 或 Embedding；
- 本地检索 + 四个本地执行器完成完整响应；
- TechnicalAgent 失败时仅 Technical 本地回退并保留案例上下文；
- QuoteAgent 失败时仅 Quote 本地回退并保留案例上下文；
- 极端历史价格不能改变 `PricingService` 的报价结果。

### 15.7 前端

- 案例列表、空态、筛选和 API 错误；
- 新增/编辑表单校验和 payload；
- 删除确认与成功刷新；
- 分析结果展示相似度、使用 Agent 和影响；
- empty/no_match/failed 文案；
- 原有本地模式提示、报价、工期和历史记录测试继续通过；
- `vue-tsc --noEmit` 和 Vite production build 通过。

自动测试全部使用临时 SQLite、Fake Runner 和 Fake Provider，不配置 Key、不产生付费调用。

## 16. 验收标准

1. 可通过 API 新增、列表、查看、完整编辑和删除历史案例。
2. 项目编号不区分大小写唯一，数据写入和读取均通过 Pydantic 校验。
3. 无 Key 时，相似检索和完整分析可离线运行，不导入或调用 Embedding 服务。
4. 固定测试语料的 Top-K 排序、阈值和并列顺序确定且可重复。
5. 流水线顺序严格变为 Requirement → Retrieval → Technical → Quote → Reply。
6. Technical 与 Quote 都收到相同的匹配案例与洞察；单步 Agent 失败后本地执行器仍收到相同上下文。
7. 最终结果逐案例展示相似度、匹配信号、使用 Agent 和影响。
8. 空库、低分和检索失败都不会阻止 Phase 1 分析结果生成。
9. `pricing_rules.json` 结果在有无案例、Agent 成功或回退时完全一致；案例只影响说明与受控工期/风险校准。
10. 案例数据库迁移失败时应用保持 Phase 1 可用，Case API 返回 503，健康状态为 degraded。
11. 旧的 `AnalysisResponse` JSON 可以读取，并自动得到 `case_rag.status=not_run`。
12. 后端和前端新增测试与全部 Phase 1 回归测试通过，生产构建成功。

## 17. 不在 Phase 2A 范围内

- OpenAI 或其他供应商的真实 Embedding 实现；
- 外部向量数据库、SQLite 向量扩展或 FTS5 索引；
- 大型本地模型、语义 reranker、交叉编码器；
- 批量 CSV/Excel 导入导出、附件和文档 OCR；
- 自动从历史 `analyses` 推断并生成案例；
- 自动修改 `pricing_rules.json` 或用历史成交价覆盖报价；
- 用户登录、权限、多租户、字段级脱敏和审计日志；
- 软删除、版本历史和案例审批流；
- Manager Agent、handoff、会话记忆和流式 RAG；
- 分布式缓存、后台索引任务和大规模性能优化；
- 真实 OpenAI 端到端测试或任何付费 API 调用。

## 18. 自审结论

- **歧义检查**：明确了金额单位、成交字段约束、PUT 语义、硬删除、Top-K、阈值、相似度公式和旧记录兼容方式。
- **遗漏检查**：覆盖数据模型、CRUD、检索 API、Provider、流水线、报价不变量、响应展示、前端、迁移失败和全部指定测试类别。
- **一致性检查**：Technical 与 Quote 消费同一案例上下文；Reply 不直接消费案例；Orchestrator 统一汇总；Agent 与本地模式保持同一契约。
- **范围检查**：Embedding 仅保留协议，不实现 Provider；没有向量库、模型安装、自动学习或 Phase 2B 内容。
- **安全检查**：无 Key 路径不会创建外部客户端；案例文本作为不可信数据；错误脱敏；不暴露真实密钥。

## 19. 待我确认的问题

以下均已采用保守默认值，不阻塞实施计划：

1. 项目编号是否由用户手工填写？默认：手工填写，大小写不敏感唯一，不自动生成业务编号。
2. 未成交案例是否允许记录“最后谈判价”？默认：不允许，`final_deal_price=null`；建议报价仍可保存。
3. 已成交但尚未交付的案例是否允许 `actual_duration_days=null`？默认：允许。
4. 删除是否需要审计或恢复？默认：Phase 2A 使用硬删除并在前端二次确认。
5. 案例规模是否会超过 2,000 条？默认：不会；超过后评估缓存、FTS5 或 Embedding Provider。
6. 默认检索参数是否接受 `top_k=5`、`min_similarity=0.25`？默认：接受，可通过环境变量调整服务默认值，但每次 API 请求仍受边界约束。
7. Technical 工期校准是否允许最多上调 20%？默认：允许，只上调最大工期且必须满足至少 2 个高质量已成交案例和超期阈值。
8. Agent 模式下是否允许把案例摘要发送给模型提供方？默认：只有用户主动配置 `OPENAI_API_KEY` 才允许，并在 README/UI 明示；无 Key 时完全本地。
