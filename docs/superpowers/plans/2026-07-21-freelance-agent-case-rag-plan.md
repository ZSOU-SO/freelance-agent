# Freelance Agent Phase 2A 历史案例 RAG 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:test-driven-development` to execute every task, and use `superpowers:verification-before-completion` before claiming completion.

**Goal:** 在不依赖 API Key、外部向量数据库或大型本地模型的前提下，为现有固定 Agent 流水线增加可管理、可检索、可解释的历史案例参考能力。

**Architecture:** 使用 SQLite 保存结构化案例；`CaseRepository` 负责持久化，`LocalBm25CaseRetrievalProvider` 负责离线检索，`CaseSearchService` 负责过滤、阈值和统一响应，`CaseInsightService` 生成确定性的案例影响摘要。Pipeline Orchestrator 在 RequirementAgent 之后检索，并只把经过 Pydantic 校验的案例上下文传给 TechnicalAgent 与 QuoteAgent。`pricing_rules.json` 与 `PricingService` 始终是报价区间唯一权威来源。

**Tech Stack:** Python 3.11+、FastAPI、Pydantic v2、SQLite、pytest、OpenAI Agents SDK（可选运行模式）、Vue 3、TypeScript、Vue Router、Vite、Vitest。

## 全局约束

- 固定顺序保持为 `RequirementAgent → 历史案例检索 → TechnicalAgent → QuoteAgent → ReplyAgent`。
- 未配置 `OPENAI_API_KEY` 时必须完整运行，案例检索始终使用免费本地实现。
- 单个 Agent 失败时继续使用对应本地执行器；案例检索失败时继续执行原 Phase 1 流水线。
- QuoteAgent 不得修改 `PricingService` 返回的最低价、最高价、币种或报价明细。
- 不接入外部向量数据库、不调用 Embedding API、不安装大型本地模型。
- 每个任务严格执行 RED → GREEN → REFACTOR；先看到指定测试失败，再写最小实现。
- 只修改当前任务列出的文件；遇到与计划不一致的现有行为时先记录证据，不扩大范围。
- 后端命令均在项目根目录执行；Windows PowerShell 使用 `\.venv\Scripts\python.exe`，其他系统可替换为对应虚拟环境 Python。

首次执行计划前只需准备免费本地开发环境；这些命令不是 Phase 2A 功能实现：

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".\backend[dev]"
npm --prefix frontend install
```

---

### Task 1：定义历史案例领域模型和兼容的分析响应模型

**涉及文件：**

- 新建：`backend/app/schemas/case.py`
- 修改：`backend/app/schemas/analysis.py`
- 修改：`backend/app/schemas/common.py`
- 修改：`backend/app/schemas/__init__.py`
- 新建：`backend/tests/unit/test_case_schemas.py`
- 修改：`backend/tests/unit/test_schemas.py`

**RED：先写失败测试**

在 `test_case_schemas.py` 覆盖：

- 合法案例可完成 Pydantic 校验。
- `project_number` 去除首尾空格并转成大写，且只允许 3～64 位 ASCII 字母、数字、点、短横线和下划线。
- `core_features`、`risks` 去空、去重并保持首次出现顺序。
- 金额使用整数人民币元，拒绝负数和小数。
- `is_won=true` 时必须有 `final_deal_price`；`is_won=false` 时该字段必须为空。
- 未成交案例不得填写 `actual_duration_days`。
- `HistoricalCaseCreate`、`HistoricalCaseUpdate`、`HistoricalCaseRead`、`HistoricalCaseSummary`、`SimilarCaseMatch` 和 `CaseRagResult` 的序列化结构固定。
- 旧的 `AnalysisResponse` JSON 不含 `case_rag` 时，反序列化后得到 `status="not_run"` 和空匹配列表。

关键测试示例：

```python
def test_won_case_requires_final_deal_price():
    payload = valid_case_payload(is_won=True, final_deal_price=None)
    with pytest.raises(ValidationError):
        HistoricalCaseCreate.model_validate(payload)


def test_old_analysis_response_defaults_case_rag(old_analysis_payload):
    response = AnalysisResponse.model_validate(old_analysis_payload)
    assert response.case_rag.status == CaseRagStatus.NOT_RUN
    assert response.case_rag.matches == []
```

**验证 RED：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_case_schemas.py backend/tests/unit/test_schemas.py -q
```

预期：因案例模型和 `AnalysisResponse.case_rag` 尚不存在而失败。

**GREEN：最小实现**

- 复用现有 `MoneyRange`、`DurationRange` 和风险模型；不要创建意义重复的金额结构。
- 新增枚举 `CaseRagStatus = not_run | matched | empty_library | no_match | failed`。
- `CaseRagResult` 至少包含 `status`、`matches`、`used_by_agents`、`impact_summary`、`retrieval_mode`、`error`。
- `SimilarCaseMatch` 至少包含案例摘要、`similarity`、分项得分、命中词、`used_by_agents` 和影响说明。
- 给 `AnalysisResponse.case_rag` 设置向后兼容的默认工厂。

核心接口：

```python
class HistoricalCaseCreate(BaseModel): ...
class HistoricalCaseUpdate(BaseModel): ...
class HistoricalCaseRead(BaseModel): ...
class SimilarCaseMatch(BaseModel): ...
class CaseRagResult(BaseModel): ...
```

**验证 GREEN：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_case_schemas.py backend/tests/unit/test_schemas.py -q
```

预期：全部通过。

**提交建议：** `feat: add historical case domain schemas`

---

### Task 2：建立版本化数据库迁移并保证迁移失败可降级启动

**涉及文件：**

- 新建：`backend/app/persistence/migrations.py`
- 修改：`backend/app/persistence/database.py`
- 修改：`backend/app/main.py`
- 修改：`backend/app/api/routes/health.py`
- 新建：`backend/tests/integration/test_case_migrations.py`
- 修改：`backend/tests/integration/test_analysis_api.py`

**RED：先写失败测试**

- 空数据库初始化后存在 `schema_migrations` 与 `historical_cases`。
- 迁移版本 `20260721_01_historical_cases` 只应用一次。
- `project_number` 大小写不敏感唯一。
- 故意注入失败 SQL 后事务回滚，不留下半张表或已登记版本。
- 案例迁移失败时应用仍能创建，原 `/health` 和分析 API 可用；健康响应新增 `case_library.status="degraded"`，案例 API 的依赖返回 503。

**验证 RED：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_case_migrations.py backend/tests/integration/test_analysis_api.py -q
```

预期：迁移器、案例表和降级健康字段不存在而失败。

**GREEN：最小实现**

- 迁移器使用一个数据库事务执行建表、索引和版本登记。
- `historical_cases` 中列表和对象字段以合法 JSON 文本保存；布尔值以 SQLite INTEGER 保存。
- 建立 `project_type`、`is_won`、`created_at` 索引和 `project_number COLLATE NOCASE UNIQUE` 约束。
- 数据库状态对象记录 `case_library_available` 与脱敏错误消息。
- 不因为案例迁移失败抛出应用启动异常；不得吞掉分析表初始化错误。

核心接口：

```python
class MigrationRunner:
    def apply(self, connection: sqlite3.Connection) -> MigrationReport: ...

@dataclass(frozen=True)
class DatabaseCapabilities:
    analyses_available: bool
    case_library_available: bool
    case_library_error: str | None
```

**验证 GREEN：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_case_migrations.py backend/tests/integration/test_analysis_api.py -q
```

预期：全部通过。

**提交建议：** `feat: add versioned historical case migration`

---

### Task 3：实现案例仓储 CRUD 和异常数据隔离

**涉及文件：**

- 新建：`backend/app/persistence/case_repository.py`
- 修改：`backend/app/persistence/__init__.py`
- 新建：`backend/tests/integration/test_case_repository.py`

**RED：先写失败测试**

- 创建案例后获得服务端生成的 UUID、`created_at`、`updated_at`。
- 按 ID 获取和按项目编号获取一致。
- 更新保留 `created_at`、刷新 `updated_at`，并支持显式清空可空字段。
- 删除返回是否实际删除，重复删除返回 `False`。
- 分页列表按 `created_at DESC, id DESC` 稳定排序，支持 `project_type`、`is_won` 和关键词过滤。
- 违反项目编号唯一约束映射为领域冲突异常。
- 手工插入损坏 JSON 后，列表返回合法记录及数据告警，不让整个列表失败；详情访问该损坏记录返回明确数据格式异常。

**验证 RED：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_case_repository.py -q
```

预期：`CaseRepository` 不存在而失败。

**GREEN：最小实现**

```python
class CaseRepository:
    def create(self, data: HistoricalCaseCreate) -> HistoricalCaseRead: ...
    def get(self, case_id: str) -> HistoricalCaseRead | None: ...
    def update(self, case_id: str, data: HistoricalCaseUpdate) -> HistoricalCaseRead | None: ...
    def delete(self, case_id: str) -> bool: ...
    def list(self, query: CaseListQuery) -> CaseListResult: ...
    def list_for_retrieval(self) -> CaseRetrievalCorpus: ...
```

- SQL 参数全部使用占位符。
- JSON 编解码集中在私有映射函数，错误转换为 `CaseDataError(case_id, field)`。
- `list_for_retrieval` 跳过损坏记录并返回 warnings，供检索遥测使用。

**验证 GREEN：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_case_repository.py -q
```

预期：全部通过。

**提交建议：** `feat: add historical case repository`

---

### Task 4：实现确定性中文友好的 Tokenizer 和本地 BM25 Provider

**涉及文件：**

- 新建：`backend/app/retrieval/__init__.py`
- 新建：`backend/app/retrieval/base.py`
- 新建：`backend/app/retrieval/tokenizer.py`
- 新建：`backend/app/retrieval/bm25_provider.py`
- 新建：`backend/tests/unit/test_case_retrieval.py`

**RED：先写失败测试**

- Tokenizer 执行 NFKC、英文小写化、保留 `vue3`、`fastapi`、`微信支付` 等技术词。
- 连续中文生成字符二元组；空白和标点变化不改变结果。
- 停用词不参与评分。
- 同类项目、功能重叠多的案例排在无关案例前。
- 重复长文本不会仅凭长度占优。
- 空语料返回空结果；单文档语料不会除零。
- 相同得分按功能得分、创建时间、项目编号稳定排序。
- 输出分数被归一化到 `[0, 1]`，同一输入重复运行完全一致。

关键排序夹具应至少包括“刷题 Web 应用”“支付商城”“硬件门禁”三个案例，并验证刷题需求命中第一个。

**验证 RED：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_case_retrieval.py -q
```

预期：检索模块不存在而失败。

**GREEN：最小实现**

```python
class CaseRetrievalProvider(Protocol):
    name: str
    def search(self, query: CaseSearchQuery, corpus: Sequence[HistoricalCaseRead]) -> list[ScoredCase]: ...

class EmbeddingProvider(Protocol):
    name: str
    def embed(self, texts: Sequence[str]) -> Sequence[Sequence[float]]: ...

class LocalBm25CaseRetrievalProvider:
    name = "local_bm25"
```

- BM25 使用 `k1=1.5`、`b=0.75`。
- 最终分数严格按设计文档计算：文本 0.45、功能 Jaccard 0.30、项目类型 0.15、风险 Jaccard 0.10。
- `EmbeddingProvider` 本阶段只有 Protocol，不创建网络客户端、不加依赖。
- 在结果中保留命中词和四个分项分数以便解释与测试。

**验证 GREEN：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_case_retrieval.py -q
```

预期：全部通过。

**提交建议：** `feat: add offline BM25 case retriever`

---

### Task 5：实现检索服务、阈值策略和确定性案例洞察

**涉及文件：**

- 新建：`backend/app/retrieval/service.py`
- 新建：`backend/app/retrieval/insights.py`
- 新建：`backend/tests/unit/test_case_search_service.py`
- 新建：`backend/tests/unit/test_case_insights.py`

**RED：先写失败测试**

- 案例库为空返回 `empty_library`，不是异常。
- 最高相似度低于 0.25 返回 `no_match`，但遥测保留候选数量和最高原始分数。
- `top_k` 默认 5，限制 1～10。
- Provider 抛错时返回 `failed` 和脱敏错误，不泄露路径、SQL 或密钥。
- 有损坏记录时跳过该记录，合法案例仍可匹配，并产生 warning。
- 只有至少两个已成交且有实际工期的匹配案例，且相似度加权超期超过 15%，才建议上调工期上限；上调最多 20%。
- 案例洞察不得产生建议报价金额或覆盖价格字段。
- 洞察输出和输入排序无关，结果可重复。

**验证 RED：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_case_search_service.py backend/tests/unit/test_case_insights.py -q
```

预期：服务和洞察类不存在而失败。

**GREEN：最小实现**

```python
class CaseSearchService:
    def search(self, query: CaseSearchQuery) -> CaseRagResult: ...

class CaseInsightService:
    def summarize(self, matches: Sequence[SimilarCaseMatch]) -> CaseInsight: ...
```

- Service 编排 repository、provider、阈值和响应模型，不把 HTTP 逻辑放入服务。
- `CaseInsight` 只包含 `duration_adjustment_percent`、`known_risks`、`technical_notes`、`quote_context_notes` 和依据案例编号。
- 所有影响说明使用模板化本地文本，避免无 Key 时产生随机结果。

**验证 GREEN：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_case_search_service.py backend/tests/unit/test_case_insights.py -q
```

预期：全部通过。

**提交建议：** `feat: add case search and insight services`

---

### Task 6：实现历史案例 CRUD API

**涉及文件：**

- 新建：`backend/app/api/routes/cases.py`
- 修改：`backend/app/api/routes/__init__.py`
- 修改：`backend/app/api/dependencies.py`
- 修改：`backend/app/main.py`
- 新建：`backend/tests/integration/test_case_api.py`

**RED：先写失败测试**

- `POST /api/v1/cases` 返回 201 和完整案例。
- `GET /api/v1/cases` 返回分页元数据、过滤结果和稳定排序。
- `GET /api/v1/cases/{id}` 返回详情；不存在返回 404。
- `PUT /api/v1/cases/{id}` 做完整更新；不存在返回 404。
- `DELETE /api/v1/cases/{id}` 返回 204；重复删除返回 404。
- 重复项目编号返回 409；非法金额、工期或成交状态返回 422。
- 案例库迁移不可用时所有案例端点返回 503 和稳定错误码 `case_library_unavailable`。

**验证 RED：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_case_api.py -q
```

预期：路由不存在或返回 404。

**GREEN：最小实现**

- Router 前缀固定为 `/api/v1/cases`。
- 使用依赖注入提供 repository 和数据库能力状态。
- HTTP 层只做模型绑定、状态码映射，不重复业务校验。
- 列表查询支持 `page`、`page_size`、`project_type`、`is_won`、`q`。

**验证 GREEN：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_case_api.py -q
```

预期：全部通过。

**提交建议：** `feat: add historical case CRUD API`

---

### Task 7：实现相似案例检索 API 和健康状态

**涉及文件：**

- 修改：`backend/app/api/routes/cases.py`
- 修改：`backend/app/api/dependencies.py`
- 修改：`backend/app/api/routes/health.py`
- 新建：`backend/tests/integration/test_case_search_api.py`
- 修改：`backend/tests/integration/test_analysis_api.py`

**RED：先写失败测试**

- `POST /api/v1/cases/search` 接收项目类型、原始需求、功能、风险、`top_k` 和阈值。
- 命中时返回相似度、分项得分、命中词、案例摘要和 `retrieval_mode="local_bm25"`。
- 空库和低相似度分别返回 200 + `empty_library`、200 + `no_match`；Provider/存储检索失败与案例基础设施不可用都返回 503 + `failed`，但流水线内部仍把同一失败结果当作非阻断降级处理。
- `top_k=0` 或大于 10 返回 422。
- 健康端点区分 `ready`、`empty`、`degraded`，不暴露数据库绝对路径。

**验证 RED：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_case_search_api.py backend/tests/integration/test_analysis_api.py -q
```

预期：search 端点和健康字段不存在而失败。

**GREEN：最小实现**

- 注入 `CaseSearchService`，避免路由直接构建 BM25 索引。
- 统一使用 Task 1 的 `CaseRagResult`，API 和 Pipeline 不创建第二套返回模型。
- 把错误分类为稳定机器码和可读中文消息。

**验证 GREEN：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_case_search_api.py backend/tests/integration/test_analysis_api.py -q
```

预期：全部通过。

**提交建议：** `feat: expose local case similarity search`

---

### Task 8：扩展 Technical 与 Quote 输入模型及本地执行器

**涉及文件：**

- 修改：`backend/app/schemas/technical.py`
- 修改：`backend/app/schemas/quote.py`
- 修改：`backend/app/executors/local/technical_executor.py`
- 修改：`backend/app/executors/local/quote_executor.py`
- 修改：`backend/tests/unit/test_local_executors.py`
- 修改：`backend/tests/unit/test_duration_rules.py`

**RED：先写失败测试**

- `TechnicalAgentInput` 和 `QuoteAgentInput` 接受已经校验的 `similar_cases` 与 `case_insight`，默认空值保持旧调用兼容。
- Technical 本地执行器按已定义门槛上调工期上限但不超过 20%，并把依据案例编号写入 `case_impacts`。
- 只有一个已成交案例、无实际工期或超期不超过 15% 时，不调整工期。
- Quote 本地执行器可引用历史成交价作为解释背景，但报价区间和明细仍完全等于 `PricingService.calculate()`。
- 本地执行器不因案例列表为空、低相似度或 warnings 失败。

关键不变量测试：

```python
assert output.quote_range == pricing_calculation.quote_range
assert output.breakdown == pricing_calculation.breakdown
assert output.currency == pricing_calculation.currency
```

**验证 RED：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_local_executors.py backend/tests/unit/test_duration_rules.py -q
```

预期：输入字段或案例影响行为不存在而失败。

**GREEN：最小实现**

- 只让 Technical 执行器应用 `CaseInsight.duration_adjustment_percent`。
- Quote 执行器只把 `quote_context_notes` 合并到解释，不读写历史价格来生成新报价。
- 输出新增默认空的 `case_impacts`，避免破坏旧测试和旧记录。

**验证 GREEN：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_local_executors.py backend/tests/unit/test_duration_rules.py -q
```

预期：全部通过。

**提交建议：** `feat: pass case insights to local technical and quote executors`

---

### Task 9：让 Agent 模式受控使用案例上下文并强化报价护栏

**涉及文件：**

- 修改：`backend/app/agents/technical_agent.py`
- 修改：`backend/app/agents/quote_agent.py`
- 修改：`backend/app/executors/agent_executor.py`
- 修改：`backend/tests/unit/test_agent_executor.py`
- 修改：`backend/tests/unit/test_quote_agent.py`
- 新建：`backend/tests/unit/test_technical_agent.py`

**RED：先写失败测试**

- TechnicalAgent 的结构化输入包含相似案例摘要和本地洞察，并要求输出逐条 `case_impacts`。
- QuoteAgent 能看到案例上下文，但系统指令明确历史价格仅用于解释。
- 模型返回自创价格时，agent executor 最终强制替换为本地 `PricingCalculation`。
- 模型返回未知案例编号、越界相似度或不合法影响结构时 Pydantic 校验失败，并触发 Quote/Technical 对应本地执行器。
- TechnicalAgent 失败不会移除已经取得的案例检索结果。
- 无 `OPENAI_API_KEY` 时不构造 Agent，不调用网络。

**验证 RED：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_agent_executor.py backend/tests/unit/test_quote_agent.py backend/tests/unit/test_technical_agent.py -q
```

预期：案例上下文提示和护栏测试失败。

**GREEN：最小实现**

- 把案例数据作为 Pydantic 输入序列化给 Agent；不要让模型自主查询数据库。
- 校验 `case_impacts[].project_number` 必须来自本次匹配集合。
- QuoteAgent 调用现有本地报价工具；executor 在模型结果校验后再次覆盖价格权威字段。
- Agent 错误进入现有 telemetry，并调用对应本地 executor。

**验证 GREEN：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_agent_executor.py backend/tests/unit/test_quote_agent.py backend/tests/unit/test_technical_agent.py -q
```

预期：全部通过。

**提交建议：** `feat: ground technical and quote agents with case context`

---

### Task 10：把案例检索接入 Pipeline Orchestrator

**涉及文件：**

- 修改：`backend/app/pipeline/orchestrator.py`
- 修改：`backend/app/pipeline/telemetry.py`
- 修改：`backend/app/schemas/analysis.py`
- 修改：`backend/tests/unit/test_pipeline.py`
- 修改：`backend/tests/integration/test_analysis_api.py`

**RED：先写失败测试**

- 调用顺序严格为 Requirement、case retrieval、Technical、Quote、Reply。
- retrieval 步骤接收 Requirement 输出，而不是未校验原始字符串拼装结果。
- 命中案例传给 Technical 与 Quote，不传给 Requirement；Reply 只接收已经汇总的上游结果。
- 结果包含匹配案例、相似度、`used_by_agents=["technical","quote"]` 和每个 Agent 的影响说明。
- `analysis_mode` 仍只表示 Agent 或本地分析；检索模式单独记录 `local_bm25`，避免混淆。
- telemetry 新增第五步 `case_retrieval`，记录耗时、状态、是否降级、warning/error。
- 空库、低相似度、检索异常都继续执行四个 Agent；检索异常的最终 `case_rag.status="failed"`。
- 单个 Agent 失败降级后，最终结果同时保留案例信息、Agent 错误和 `fallback_occurred=true`。
- Quote 输出始终满足报价工具不变量。

**验证 RED：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_pipeline.py backend/tests/integration/test_analysis_api.py -q
```

预期：编排顺序、第五步遥测和最终结果字段测试失败。

**GREEN：最小实现**

伪代码顺序必须保持：

```python
requirement = validate(await run_requirement(request))
case_rag = await retrieve_cases(requirement)
case_insight = summarize(case_rag.matches)
technical = validate(await run_technical(requirement, case_rag, case_insight))
pricing = pricing_service.calculate(requirement, technical)
quote = validate(await run_quote(requirement, technical, pricing, case_rag, case_insight))
reply = validate(await run_reply(requirement, technical, quote))
return orchestrator.build_response(...)
```

- `retrieve_cases` 捕获自身异常并返回 `CaseRagResult.failed`，不能跳出整条流水线。
- 最终统一响应只由 orchestrator 创建。
- 不改变现有四个 Agent 的失败降级策略。

**验证 GREEN：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/unit/test_pipeline.py backend/tests/integration/test_analysis_api.py -q
```

预期：全部通过。

**提交建议：** `feat: integrate historical case retrieval into pipeline`

---

### Task 11：验证增强分析记录的持久化与旧记录兼容

**涉及文件：**

- 修改：`backend/app/persistence/analysis_repository.py`
- 修改：`backend/tests/integration/test_analysis_repository.py`
- 修改：`backend/tests/integration/test_analysis_api.py`

**RED：先写失败测试**

- 新分析保存后再读取，`case_rag`、相似度、使用 Agent、影响和检索遥测无损。
- 手工保存一条 Phase 1 JSON（无 `case_rag`、只有四步 telemetry），列表和详情仍可读取。
- 损坏的新增案例字段不应影响其他分析记录返回；该记录产生可识别的数据错误。
- 未配置 API Key 的完整 API 分析、保存、列表、详情均通过且无网络 mock 被调用。

**验证 RED：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_analysis_repository.py backend/tests/integration/test_analysis_api.py -q
```

预期：增强字段往返或旧记录兼容测试失败。

**GREEN：最小实现**

- 继续使用整个 `AnalysisResponse` JSON 持久化，不拆出第二套案例关联表。
- 读取旧 JSON 时依赖 Task 1 默认值，不做破坏性数据回填。
- 明确处理 Pydantic 校验异常，避免列表端点整体 500。

**验证 GREEN：**

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/integration/test_analysis_repository.py backend/tests/integration/test_analysis_api.py -q
```

预期：全部通过。

**提交建议：** `test: cover case RAG analysis persistence compatibility`

---

### Task 12：实现前端路由、案例列表和案例编辑表单

**涉及文件：**

- 修改：`frontend/package.json`
- 修改：`frontend/package-lock.json`
- 修改：`frontend/src/main.ts`
- 修改：`frontend/src/App.vue`
- 新建：`frontend/src/router/index.ts`
- 新建：`frontend/src/types/case.ts`
- 新建：`frontend/src/api/cases.ts`
- 新建：`frontend/src/composables/useCases.ts`
- 新建：`frontend/src/views/AnalysisView.vue`
- 新建：`frontend/src/views/CaseListView.vue`
- 新建：`frontend/src/views/CaseFormView.vue`
- 新建：`frontend/src/components/CaseTable.vue`
- 新建：`frontend/src/components/CaseForm.vue`
- 新建：`frontend/src/components/CaseDetail.vue`
- 新建：`frontend/src/tests/CaseListView.spec.ts`
- 新建：`frontend/src/tests/CaseForm.spec.ts`
- 修改：`frontend/vite.config.ts`

**RED：先写失败测试**

- 顶部导航可进入“需求分析”和“历史案例”。
- `/cases` 加载分页列表，展示编号、类型、报价、成交价、工期、风险、成交状态。
- 空列表显示可操作空状态；API 503 显示案例库不可用但不影响分析入口。
- `/cases/new` 创建合法案例；成交开关控制最终成交价和实际工期规则。
- `/cases/:id/edit` 载入并完整更新案例。
- 删除前二次确认，成功后刷新；取消不调用 API。
- 表单金额使用整数元，数组字段可增删且提交前清理空项。

**验证 RED：**

```powershell
npm --prefix frontend test -- --run src/tests/CaseListView.spec.ts src/tests/CaseForm.spec.ts
```

预期：路由、页面和组件不存在而失败。

**GREEN：最小实现**

- 添加 `vue-router` 并锁定版本；不引入状态管理库。
- 把现有分析页面内容移动到 `AnalysisView.vue`，保持行为和样式。
- `cases.ts` 只负责 HTTP 和响应类型；状态、错误、加载逻辑放在 composable。
- 表单复用同一个组件处理新增和编辑，以路由参数决定模式。

**验证 GREEN：**

```powershell
npm --prefix frontend test -- --run src/tests/CaseListView.spec.ts src/tests/CaseForm.spec.ts
npm --prefix frontend run build
```

预期：组件测试通过，TypeScript 与 Vite 构建成功。

**提交建议：** `feat: add historical case management UI`

---

### Task 13：展示相似案例、完成全量回归和文档验收

**涉及文件：**

- 新建：`frontend/src/components/SimilarCasesPanel.vue`
- 新建：`frontend/src/components/CaseRagStatus.vue`
- 修改：`frontend/src/components/AnalysisResult.vue`
- 修改：`frontend/src/components/StepTelemetry.vue`
- 修改：`frontend/src/types/analysis.ts`
- 新建：`frontend/src/tests/SimilarCasesPanel.spec.ts`
- 修改：`frontend/src/tests/AnalysisResult.spec.ts`
- 修改：`README.md`
- 修改：`docs/superpowers/specs/2026-07-21-freelance-agent-case-rag-design.md`（仅在实现事实与设计存在经批准差异时更新）

**RED：先写失败测试**

- 分析结果展示匹配案例、百分比相似度、命中词、成交信息、被哪些 Agent 使用和具体影响。
- `empty_library`、`no_match`、`failed` 使用不同的非阻塞提示。
- 检索失败提示不掩盖正常的技术方案、报价和客户回复。
- 遥测显示 `case_retrieval` 耗时、模式和 warning/error。
- 本地分析仍显示“本地规则分析，未调用大模型”；案例检索标签显示“本地 BM25”。
- 旧的分析记录没有 `case_rag` 时组件不报错，显示“该记录未执行案例检索”。

**验证 RED：**

```powershell
npm --prefix frontend test -- --run src/tests/SimilarCasesPanel.spec.ts src/tests/AnalysisResult.spec.ts
```

预期：组件和新展示行为不存在而失败。

**GREEN：最小实现**

- 将案例展示作为 `AnalysisResult` 的独立区块，不把其报价混入权威报价卡片。
- 只显示 API 返回的解释，不在前端重新计算相似度或工期影响。
- README 增加案例 CRUD、离线检索、迁移、无 Key 运行和新测试命令。

**局部验证：**

```powershell
npm --prefix frontend test -- --run src/tests/SimilarCasesPanel.spec.ts src/tests/AnalysisResult.spec.ts
```

预期：通过。

**全量验证：**

```powershell
Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
.\.venv\Scripts\python.exe -m pytest backend/tests -q
npm --prefix frontend test -- --run
npm --prefix frontend run build
```

预期：后端、前端测试和构建全部通过；输出中无真实 API Key、无网络调用。

**手工冒烟验证：**

```powershell
.\.venv\Scripts\python.exe -m uvicorn backend.app.main:create_app --factory --host 127.0.0.1 --port 8000
```

另开终端：

```powershell
npm --prefix frontend run dev -- --host 127.0.0.1
```

依次验证：创建三条案例 → 编辑一条 → 搜索刷题类需求 → 执行分析 → 查看相似案例及影响 → 删除测试案例。确认报价区间与 `backend/pricing_rules.json` 规则一致。

**最终验收检查：**

- [ ] 无 API Key 完整运行且不尝试网络请求。
- [ ] 案例 CRUD、搜索、Pipeline、持久化全部通过自动测试。
- [ ] Agent 模式和本地模式返回统一结构。
- [ ] 案例检索失败不会中断原流水线。
- [ ] 报价金额仅来自 `PricingService`。
- [ ] 旧分析记录可读。
- [ ] 数据库迁移失败时 Phase 1 可用、案例模块明确降级。
- [ ] 前端清楚区分分析模式和检索模式。
- [ ] README 不含密钥、真实客户资料或本机绝对路径。
- [ ] `git diff --check` 无空白错误，`git status --short` 只包含计划内文件。

**提交建议：** `feat: complete historical case RAG phase 2A`

---

## 实施顺序与检查点

共 13 个开发任务，必须顺序执行。Task 1～7 完成后做后端案例模块检查点；Task 8～11 完成后做流水线与无 Key 检查点；Task 12～13 完成后做前端和全量验收。任一检查点未通过，不进入下一个检查点。

每个检查点记录：执行命令、通过/失败数量、失败原因、是否出现范围变更。不得用跳过测试、放宽断言或捕获所有异常的方式制造绿灯。

## 计划自审

- TDD：每项任务都有可观察的 RED、最小 GREEN 和验证命令。
- 架构边界：Repository、Provider、Service、Orchestrator、HTTP 和 UI 职责分开。
- 报价边界：历史案例没有价格写入路径，Quote 的权威字段会被本地计算再次覆盖。
- 降级边界：区分 Agent 降级、案例检索软失败、案例迁移基础设施失败。
- 兼容性：Pydantic 默认值保护旧调用和旧分析 JSON；迁移为新增表而非破坏性改表。
- 范围控制：Embedding 只有 Protocol；没有外部向量库、模型安装、Manager Agent、handoff 或自动学习。
- 可执行性：所有任务列出文件、测试、实现约束和命令，不使用“类似处理”或未定义占位步骤。

## 待我确认的问题

以下问题按保守默认值写入计划，实施前可集中确认；未确认时按括号内默认值执行：

1. 金额单位是否统一为人民币整数元？（默认：是，不保存分。）
2. 项目编号是否允许人工填写且全局唯一？（默认：是，大小写不敏感。）
3. 未成交案例是否允许记录实际投入工期？（默认：不允许；如需复盘内部投入，应新增独立字段而非复用实际工期。）
4. 案例管理是否需要登录和权限控制？（默认：Phase 2A 仅本机单用户，不加鉴权，但服务只监听 `127.0.0.1`。）
5. Agent 模式是否允许把匹配案例摘要发送给 OpenAI？（默认：允许发送最小必要摘要，不发送客户姓名、联系方式或附件；UI/README 明示。）
6. 默认相似度阈值 0.25、默认返回 5 条是否合适？（默认：按此实施，并做成应用配置。）
7. 工期校准是否可以只上调、不下调？（默认：只上调且最多 20%，避免案例噪声导致过度乐观。）
8. 删除是否需要软删除与恢复？（默认：Phase 2A 使用硬删除并二次确认；备份、审计日志不在本阶段。）
