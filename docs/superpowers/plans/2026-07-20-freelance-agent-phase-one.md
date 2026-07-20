# Freelance Agent Phase One Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Git commit steps are intentionally omitted because the user will commit manually after verification.

**Goal:** Build a tested FastAPI and Vue 3 application that analyzes freelance requirements through four ordered OpenAI Agents SDK stages or an automatic, API-key-free local fallback pipeline.

**Architecture:** A Python Pipeline Orchestrator owns the fixed stage order and validates independent Pydantic contracts between stages. Agent adapters and deterministic local executors implement the same stage protocol; every Agent failure falls back only that stage. A local pricing service is the sole authority for quote amounts, SQLite stores the unified response, and Vue consumes the same contract in every mode.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic 2, OpenAI Agents SDK, SQLite, pytest, HTTPX, Vue 3, TypeScript, Vite, Vitest, Vue Test Utils.

## Global Constraints

- Stage order is exactly `RequirementAgent -> TechnicalAgent -> QuoteAgent -> ReplyAgent`.
- `pricing_rules.json` is authoritative for CNY pre-tax quote ranges.
- No `OPENAI_API_KEY` must be required for import, startup, tests, or local analysis.
- Every stage has independent input and output Pydantic models.
- Agent failures must record sanitized errors and fall back only the failed stage.
- `analysis_mode` is `agents` when a key selected Agent execution and `local_fallback` when no key selected local execution.
- A mixed Agent run keeps `analysis_mode: agents` and reports `fallback_occurred: true`.
- Manager Agent and handoffs are not implemented in phase one.
- Do not write to `.git`; the user will commit manually.

---

### Task 1: Backend contracts, configuration, and pricing rules

**Files:**
- Create: `backend/pyproject.toml`
- Create: `backend/pricing_rules.json`
- Create: `backend/app/__init__.py`
- Create: `backend/app/core/config.py`
- Create: `backend/app/schemas/common.py`
- Create: `backend/app/schemas/requirement.py`
- Create: `backend/app/schemas/technical.py`
- Create: `backend/app/schemas/quote.py`
- Create: `backend/app/schemas/reply.py`
- Create: `backend/app/schemas/analysis.py`
- Test: `backend/tests/unit/test_schemas.py`

**Interfaces:**
- Produces: `Settings.from_env()`, all four Agent input/output models, `PricingCalculation`, `AnalysisResponse`, `StepTelemetry`, and `AnalysisMode`.

- [ ] **Step 1: Write failing contract tests**

```python
def test_requirement_text_cannot_be_blank():
    with pytest.raises(ValidationError):
        RequirementAgentInput(requirement_text="   ")

def test_analysis_response_accepts_agents_and_local_modes(sample_response_data):
    assert AnalysisResponse(**sample_response_data, analysis_mode="agents")
    assert AnalysisResponse(**sample_response_data, analysis_mode="local_fallback")
```

- [ ] **Step 2: Run the tests and confirm failure**

Run: `python -m pytest backend/tests/unit/test_schemas.py -q`

Expected: collection fails because `backend.app.schemas` does not exist.

- [ ] **Step 3: Implement immutable validated contracts and environment settings**

Use Pydantic models with `extra="forbid"`, non-negative monetary values, positive duration ranges, `min <= max` validators, and literals/enums for modes and risk categories. `Settings.from_env()` treats a blank key as absent and resolves a configurable SQLite path.

- [ ] **Step 4: Add validated local pricing configuration**

`pricing_rules.json` defines project base ranges, feature additions, risk fees, risk multipliers, urgent-delivery multipliers, a `CNY` currency, and a rounding unit. No price values live in Agent prompts.

- [ ] **Step 5: Run the contract tests**

Run: `python -m pytest backend/tests/unit/test_schemas.py -q`

Expected: PASS.

### Task 2: Deterministic pricing, risk, and duration services

**Files:**
- Create: `backend/app/services/__init__.py`
- Create: `backend/app/services/pricing.py`
- Create: `backend/app/services/risk_rules.py`
- Create: `backend/app/services/duration_rules.py`
- Test: `backend/tests/unit/test_pricing.py`
- Test: `backend/tests/unit/test_risk_rules.py`
- Test: `backend/tests/unit/test_duration_rules.py`

**Interfaces:**
- Consumes: `RequirementAgentOutput`, `RiskItem`, and pricing JSON.
- Produces: `PricingService.calculate(requirement, risks) -> PricingCalculation`, `detect_risks(text) -> list[RiskItem]`, and `estimate_duration(project_type, features, urgent) -> DurationEstimate`.

- [ ] **Step 1: Write failing deterministic service tests**

```python
def test_pricing_uses_base_features_and_urgent_multiplier(pricing_service, requirement):
    result = pricing_service.calculate(requirement, [urgent_risk])
    assert result.currency == "CNY"
    assert result.min_amount == 24000
    assert result.max_amount == 42000
    assert [item.code for item in result.calculation_items] == [
        "base:web_app", "feature:payment", "risk:urgent_delivery"
    ]

@pytest.mark.parametrize("text, category", [
    ("完成后再付款", "payment"),
    ("需要对接蓝牙硬件", "hardware"),
    ("接入微信支付", "third_party_platform"),
    ("三天内必须上线", "urgent_delivery"),
])
def test_detects_required_risk_categories(text, category):
    assert category in {risk.category for risk in detect_risks(text)}
```

- [ ] **Step 2: Confirm service tests fail**

Run: `python -m pytest backend/tests/unit/test_pricing.py backend/tests/unit/test_risk_rules.py backend/tests/unit/test_duration_rules.py -q`

Expected: imports fail because services do not exist.

- [ ] **Step 3: Implement deterministic services**

Pricing must load and validate rules once, list every calculation item, apply fixed additions before multipliers, and round outward so the minimum is rounded down and maximum up. Risk matching is case-insensitive and deduplicated by category. Duration combines project and feature working-day ranges, then applies urgency compression without returning zero days.

- [ ] **Step 4: Run service tests**

Run: `python -m pytest backend/tests/unit/test_pricing.py backend/tests/unit/test_risk_rules.py backend/tests/unit/test_duration_rules.py -q`

Expected: PASS.

### Task 3: Four local stage executors

**Files:**
- Create: `backend/app/executors/__init__.py`
- Create: `backend/app/executors/base.py`
- Create: `backend/app/executors/local/__init__.py`
- Create: `backend/app/executors/local/requirement_executor.py`
- Create: `backend/app/executors/local/technical_executor.py`
- Create: `backend/app/executors/local/quote_executor.py`
- Create: `backend/app/executors/local/reply_executor.py`
- Test: `backend/tests/unit/test_local_executors.py`

**Interfaces:**
- Produces: async `execute(input_model) -> output_model` on each local executor and `StageExecutor[InputT, OutputT]` protocol.
- Consumes: deterministic services from Task 2.

- [ ] **Step 1: Write failing executor tests**

```python
async def test_requirement_executor_extracts_type_features_budget_and_deadline():
    result = await executor.execute(RequirementAgentInput(
        requirement_text="做一个带微信支付的商城，预算3到5万，4周上线"
    ))
    assert result.project_type == "ecommerce"
    assert "payment" in result.features
    assert result.client_budget.min_amount == 30000
    assert result.desired_deadline.max_days == 20

async def test_quote_executor_uses_pricing_service(local_quote_input):
    output = await executor.execute(local_quote_input)
    assert output.pricing.currency == "CNY"
    assert "本地报价规则" in output.explanation
```

- [ ] **Step 2: Confirm executor tests fail**

Run: `python -m pytest backend/tests/unit/test_local_executors.py -q`

Expected: imports fail because local executors do not exist.

- [ ] **Step 3: Implement the executors**

Requirement uses normalized keyword maps and amount/duration regexes. Technical uses project templates plus risk and duration services. Quote delegates every amount to `PricingService`. Reply generates questions only for missing information and a Chinese client reply containing the locked range and duration.

- [ ] **Step 4: Run executor tests**

Run: `python -m pytest backend/tests/unit/test_local_executors.py -q`

Expected: PASS.

### Task 4: OpenAI Agents SDK adapters

**Files:**
- Create: `backend/app/agents/__init__.py`
- Create: `backend/app/agents/requirement_agent.py`
- Create: `backend/app/agents/technical_agent.py`
- Create: `backend/app/agents/quote_agent.py`
- Create: `backend/app/agents/reply_agent.py`
- Create: `backend/app/executors/agent_executor.py`
- Test: `backend/tests/unit/test_agent_executor.py`
- Test: `backend/tests/unit/test_quote_agent.py`

**Interfaces:**
- Produces: four lazy Agent factories and four stage adapters implementing `StageExecutor`.
- Consumes: a runner callable compatible with `await Runner.run(agent, input)` so tests can inject a fake.

- [ ] **Step 1: Write failing adapter tests with a fake runner**

```python
async def test_agent_adapter_validates_final_output(fake_runner):
    fake_runner.final_output = valid_requirement_output.model_dump()
    result = await adapter.execute(requirement_input)
    assert result == valid_requirement_output

async def test_quote_agent_must_capture_local_tool_result(quote_adapter):
    with pytest.raises(QuoteToolNotCalledError):
        await quote_adapter.execute(quote_input, runner=runner_that_skips_tool)
```

- [ ] **Step 2: Confirm adapter tests fail**

Run: `python -m pytest backend/tests/unit/test_agent_executor.py backend/tests/unit/test_quote_agent.py -q`

Expected: imports fail because Agent adapters do not exist.

- [ ] **Step 3: Implement lazy Agent factories and adapters**

Import `agents.Agent`, `agents.Runner`, and `agents.function_tool` only inside Agent-mode construction paths. Each factory supplies an explicit Pydantic `output_type`. The Quote Agent receives a `calculate_quote` function tool backed by `PricingService`; the adapter rejects a run when stage context has no captured `PricingCalculation`. The public quote is rebuilt from the captured calculation, never from model-authored numbers.

- [ ] **Step 4: Run Agent adapter tests without an API key**

Run: `$env:OPENAI_API_KEY=''; python -m pytest backend/tests/unit/test_agent_executor.py backend/tests/unit/test_quote_agent.py -q`

Expected: PASS without network access.

### Task 5: Pipeline Orchestrator, validation, fallback, and telemetry

**Files:**
- Create: `backend/app/pipeline/__init__.py`
- Create: `backend/app/pipeline/telemetry.py`
- Create: `backend/app/pipeline/orchestrator.py`
- Test: `backend/tests/unit/test_pipeline.py`

**Interfaces:**
- Produces: `PipelineOrchestrator.analyze(requirement_text) -> AnalysisResponse`.
- Consumes: four primary executors, four local executors, settings, a clock, and an identifier factory.

- [ ] **Step 1: Write failing pipeline tests**

```python
async def test_no_key_runs_four_local_steps_in_order(orchestrator, call_log):
    result = await orchestrator.analyze("开发一个企业官网")
    assert call_log == ["requirement", "technical", "quote", "reply"]
    assert result.analysis_mode == "local_fallback"
    assert result.fallback_occurred is False

async def test_one_agent_failure_falls_back_only_that_stage(agent_orchestrator):
    agent_orchestrator.technical_agent.side_effect = RuntimeError("provider unavailable")
    result = await agent_orchestrator.analyze("开发一个商城")
    assert result.analysis_mode == "agents"
    assert result.fallback_occurred is True
    assert result.telemetry.steps[1].execution_mode == "local_fallback"
    assert result.telemetry.steps[1].error == "RuntimeError: provider unavailable"
```

- [ ] **Step 2: Confirm pipeline tests fail**

Run: `python -m pytest backend/tests/unit/test_pipeline.py -q`

Expected: import fails because the orchestrator does not exist.

- [ ] **Step 3: Implement ordered execution and stage fallback**

Use one private `_run_stage` helper that times the primary call, validates the output model, sanitizes any exception, and runs the matching local executor. Assemble the final response only after all four validated outputs exist. Preserve the locked pricing calculation when building `QuoteResult`.

- [ ] **Step 4: Run pipeline tests**

Run: `python -m pytest backend/tests/unit/test_pipeline.py -q`

Expected: PASS.

### Task 6: SQLite repository and FastAPI API

**Files:**
- Create: `backend/app/persistence/__init__.py`
- Create: `backend/app/persistence/database.py`
- Create: `backend/app/persistence/analysis_repository.py`
- Create: `backend/app/api/__init__.py`
- Create: `backend/app/api/dependencies.py`
- Create: `backend/app/api/routes/__init__.py`
- Create: `backend/app/api/routes/analyses.py`
- Create: `backend/app/api/routes/health.py`
- Create: `backend/app/main.py`
- Create: `backend/tests/conftest.py`
- Test: `backend/tests/integration/test_analysis_repository.py`
- Test: `backend/tests/integration/test_analysis_api.py`

**Interfaces:**
- Produces: `create_app(settings=None) -> FastAPI`, repository `save`, `list`, and `get` methods, plus four HTTP endpoints.
- Consumes: `PipelineOrchestrator` and `AnalysisResponse`.

- [ ] **Step 1: Write failing repository and API tests**

```python
def test_post_analysis_persists_unified_result(client):
    response = client.post("/api/v1/analyses", json={"requirement_text": "开发企业官网"})
    assert response.status_code == 201
    body = response.json()
    assert body["analysis_mode"] == "local_fallback"
    assert client.get(f"/api/v1/analyses/{body['id']}").json() == body

def test_health_reports_local_mode_without_key(client):
    assert client.get("/api/v1/health").json()["analysis_mode"] == "local_fallback"
```

- [ ] **Step 2: Confirm integration tests fail**

Run: `python -m pytest backend/tests/integration -q`

Expected: import fails because the application factory does not exist.

- [ ] **Step 3: Implement persistence and API**

Use parameterized `sqlite3` queries, one connection per operation, UTC ISO timestamps, JSON serialization through Pydantic, and newest-first pagination. `create_app` initializes the database and services without constructing an OpenAI client. Add CORS for the configured local frontend origin.

- [ ] **Step 4: Run integration and backend tests**

Run: `python -m pytest backend/tests -q`

Expected: PASS.

### Task 7: Vue 3 TypeScript frontend

**Files:**
- Create: `frontend/package.json`
- Create: `frontend/tsconfig.json`
- Create: `frontend/vite.config.ts`
- Create: `frontend/index.html`
- Create: `frontend/src/main.ts`
- Create: `frontend/src/App.vue`
- Create: `frontend/src/style.css`
- Create: `frontend/src/types/analysis.ts`
- Create: `frontend/src/api/analyses.ts`
- Create: `frontend/src/composables/useAnalysis.ts`
- Create: `frontend/src/components/RequirementForm.vue`
- Create: `frontend/src/components/AnalysisModeBadge.vue`
- Create: `frontend/src/components/AnalysisResult.vue`
- Create: `frontend/src/components/AnalysisHistory.vue`
- Create: `frontend/src/components/StepTelemetry.vue`
- Test: `frontend/src/tests/RequirementForm.spec.ts`
- Test: `frontend/src/tests/AnalysisResult.spec.ts`

**Interfaces:**
- Produces: a responsive single-page UI consuming `POST/GET /api/v1/analyses`.
- Consumes: TypeScript equivalents of `AnalysisResponse` with no mode-specific transport type.

- [ ] **Step 1: Write failing component tests**

```typescript
it('emits trimmed requirement text', async () => {
  const wrapper = mount(RequirementForm)
  await wrapper.get('textarea').setValue('  开发商城  ')
  await wrapper.get('form').trigger('submit')
  expect(wrapper.emitted('submit')?.[0]).toEqual(['开发商城'])
})

it('shows the required local fallback notice', () => {
  const wrapper = mount(AnalysisResult, { props: { analysis: localResult } })
  expect(wrapper.text()).toContain('本地规则分析，未调用大模型')
})
```

- [ ] **Step 2: Confirm frontend tests fail**

Run: `npm --prefix frontend test -- --run`

Expected: component imports fail because the components do not exist.

- [ ] **Step 3: Implement the frontend**

Create an accessible form, loading and error states, mode badge, local notice, quote and duration cards, risk severity display, recommendation, follow-up questions, copyable client reply, ordered telemetry, and history selection. Keep API base URL configurable through `VITE_API_BASE_URL`.

- [ ] **Step 4: Run frontend tests and production build**

Run: `npm --prefix frontend test -- --run`

Expected: PASS.

Run: `npm --prefix frontend run build`

Expected: PASS and `frontend/dist` created.

### Task 8: README, end-to-end checks, and final verification

**Files:**
- Modify: `README.md`
- Modify: `.env.example`
- Test: all backend and frontend tests.

**Interfaces:**
- Produces: reproducible setup and verification instructions for Windows, macOS, and Linux.

- [ ] **Step 1: Expand README**

Document architecture, exact prerequisites, backend and frontend install commands, environment variables, Agents and local modes, pricing-rule format, API endpoints, test commands, example request/response, limitations, and future Manager/handoff extension points.

- [ ] **Step 2: Verify backend without an API key**

Run: `$env:OPENAI_API_KEY=''; python -m pytest backend/tests -q`

Expected: all backend tests PASS.

Run: `$env:OPENAI_API_KEY=''; python -c "from backend.app.main import create_app; app=create_app(); print(app.title)"`

Expected: prints `freelance-agent` without credential errors.

- [ ] **Step 3: Verify frontend**

Run: `npm --prefix frontend test -- --run`

Expected: all frontend tests PASS.

Run: `npm --prefix frontend run build`

Expected: production build PASS.

- [ ] **Step 4: Run the full backend suite with warnings visible**

Run: `python -m pytest backend/tests -ra`

Expected: PASS with no unexpected warnings.

- [ ] **Step 5: Review deliverables**

Confirm that no secret is present, `.env` and SQLite files are ignored, all four ordered stages have tests, all local executors have tests, the Quote Agent cannot override prices, the API persists completed analyses, and the final report lists changed files, verification results, and unresolved issues.
