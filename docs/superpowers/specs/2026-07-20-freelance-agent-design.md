# Freelance Agent Phase One Design

## 1. Objective

Build a full-stack application named `freelance-agent` for analyzing freelance client requirements. The backend uses Python, FastAPI, SQLite, and the OpenAI Agents SDK. The frontend uses Vue 3 and TypeScript.

Phase one must accept requirement text, extract structured project information, calculate a deterministic CNY quotation from local rules, detect delivery and commercial risks, produce an acceptance recommendation and client reply, and persist every completed analysis.

## 2. Fixed Constraints

- Agent execution order is `RequirementAgent -> TechnicalAgent -> QuoteAgent -> ReplyAgent`.
- Python code, not an LLM, controls the pipeline order.
- Each agent has independent Pydantic input and output models.
- Every step output is validated before it can become the next step's input.
- The final API result is assembled only by the Pipeline Orchestrator.
- Manager Agent and handoffs are outside phase-one scope.
- All quotations use CNY and represent pre-tax ranges.
- `pricing_rules.json` is the authority for the final quotation range.
- An LLM may explain a quotation but cannot change its minimum, maximum, or currency.
- The application starts and remains usable without `OPENAI_API_KEY`.
- Agent and local modes expose the same API response schema.

## 3. Execution Modes

### 3.1 Agents mode

When `OPENAI_API_KEY` is non-empty, the orchestrator sets `analysis_mode` to `agents` and attempts the four Agents SDK steps in fixed order.

If one agent raises an exception, times out, returns invalid structured output, or violates a stage invariant, the orchestrator records the error and executes that stage's matching local executor. Later stages continue with the validated fallback result.

A mixed run keeps `analysis_mode: agents`, sets `fallback_occurred: true`, and identifies the locally executed step in telemetry. This preserves the distinction between the requested run mode and actual per-step execution.

### 3.2 Local fallback mode

When `OPENAI_API_KEY` is empty or absent, the orchestrator sets `analysis_mode` to `local_fallback` and uses local executors for all four stages. OpenAI client construction and Agents SDK imports that require credentials are deferred until an Agent execution is requested.

The frontend displays `本地规则分析，未调用大模型` whenever `analysis_mode` is `local_fallback`.

## 4. Pipeline Stages

### 4.1 Requirement stage

`RequirementAgentInput` contains the raw requirement text.

`RequirementAgentOutput` contains:

- normalized project type;
- normalized feature names;
- optional client budget range and original budget text;
- optional desired duration and original deadline text;
- detected risk signals;
- missing information.

The local executor uses Chinese and English keyword dictionaries plus regular expressions for currencies, amount units, calendar dates, and duration expressions.

### 4.2 Technical stage

`TechnicalAgentInput` contains a validated `RequirementAgentOutput`.

`TechnicalAgentOutput` contains:

- recommended frontend, backend, database, deployment, and integration technologies;
- an architecture summary;
- deliverables;
- minimum and maximum duration in working days;
- normalized risks;
- an acceptance verdict and reasons.

The minimum risk categories are payment, hardware, third-party platform, and urgent delivery. The local executor uses project templates, feature complexity scores, duration rules, and risk keywords.

### 4.3 Quote stage

`QuoteAgentInput` contains validated requirement and technical outputs.

The QuoteAgent is configured with a local `calculate_quote` function tool. The tool reads validated in-memory pricing configuration loaded from `backend/pricing_rules.json`, calculates a quote, and stores the authoritative `PricingCalculation` in the stage context.

The stage is invalid unless the pricing tool produced a valid result. `QuoteAgentOutput` contains explanation, assumptions, and recommended payment terms, but does not own editable price fields. The orchestrator constructs the public `QuoteResult` from `PricingCalculation` plus the validated explanation.

The local quote executor calls the same pricing service directly, so both modes use identical price mathematics.

The calculation order is:

1. select the project-type base minimum and maximum;
2. add configured feature minimum and maximum amounts;
3. add configured fixed risk fees;
4. apply risk and urgent-delivery multipliers;
5. round the final range using the rule file's rounding unit;
6. guarantee `min_amount <= max_amount` and `currency == CNY`.

### 4.4 Reply stage

`ReplyAgentInput` contains all validated stage data, including the locked quote.

`ReplyAgentOutput` contains:

- follow-up questions;
- a client-facing Chinese reply;
- final recommendation wording consistent with the technical verdict.

The local executor uses deterministic templates and never invents missing scope details.

## 5. Unified Result Contract

`AnalysisResponse` contains:

- `id` and `created_at`;
- original `requirement_text`;
- `analysis_mode`, either `agents` or `local_fallback`;
- `fallback_occurred`;
- structured `requirement`;
- `technical_solution`;
- authoritative `quote`;
- `estimated_duration`;
- normalized `risks`;
- `recommendation` with `should_accept`, verdict, and reasons;
- `follow_up_questions`;
- `client_reply`;
- `telemetry` with total duration and four ordered step records.

Each step telemetry record contains its stage name, actual execution mode, elapsed milliseconds, fallback flag, and sanitized optional error message. Secrets, stack traces, and raw API responses are not returned to the frontend.

## 6. Error Handling

- Empty or whitespace-only input is rejected by FastAPI with status 422.
- Invalid Agent output triggers only the corresponding local executor.
- Agent errors are logged with the stage and correlation identifier.
- If the matching local executor also fails, the pipeline returns a controlled 500 response and logs both failures.
- Pricing configuration is validated at application startup. Invalid local pricing rules are a startup configuration error because no valid quotation can be produced.
- Database write failure returns a controlled server error instead of claiming an analysis was saved.
- History list data is validated when deserialized from SQLite.

## 7. Persistence and API

SQLite access is isolated behind `AnalysisRepository`. Each operation opens its own connection and uses parameterized SQL. The schema stores the identifier, original requirement text, complete result JSON, analysis mode, fallback flag, and UTC creation time.

Phase-one endpoints are:

- `POST /api/v1/analyses` to analyze and persist one request;
- `GET /api/v1/analyses` to return paginated newest-first history;
- `GET /api/v1/analyses/{id}` to return one complete record;
- `GET /api/v1/health` to report health and the current default analysis mode.

## 8. Frontend

The Vue 3 TypeScript interface provides:

- a requirement text form;
- loading, validation, and API error states;
- an analysis-mode badge and local fallback notice;
- project summary, technical solution, quote, duration, risks, recommendation, questions, and client reply;
- per-step telemetry details;
- persisted analysis history and record selection.

The frontend consumes a single generated-equivalent TypeScript contract matching `AnalysisResponse`; it contains no mode-specific response parsing.

## 9. Testing Strategy

Backend unit tests cover:

- pricing base amounts, feature additions, risk fees, multipliers, rounding, and invalid rules;
- all four risk categories;
- duration calculation;
- each of the four local executors;
- each Agent adapter with a mocked runner;
- structured-output validation;
- QuoteAgent tool invocation and locked-price invariants;
- pipeline order, no-key mode, per-stage fallback, telemetry, and total failure handling.

Integration tests cover SQLite persistence and all API endpoints using a temporary database. Agent calls are mocked; automated tests do not require a live API key.

Frontend tests cover requirement submission, result rendering, the local-mode message, fallback telemetry, and error states. The production frontend build must also pass.

## 10. Extension Boundaries

The executor protocol hides whether a stage is implemented locally, through the OpenAI Agents SDK, or through a future provider. The orchestrator depends on that protocol rather than concrete agents.

Future Manager Agent or handoff orchestration can be added as another pipeline strategy without changing public schemas, pricing authority, persistence, or frontend behavior.

## 11. Delivery Sequence

1. Create and commit repository initialization files.
2. Commit this approved design specification.
3. Write the detailed test-driven implementation plan.
4. Implement backend schemas and configuration.
5. Implement and test deterministic pricing, risk, and duration rules.
6. Implement and test four local executors.
7. Implement and test four Agents SDK adapters.
8. Implement and test the orchestrator, validation, fallback, and telemetry.
9. Implement and test SQLite persistence and FastAPI endpoints.
10. Implement and test the Vue 3 frontend.
11. Complete README instructions and run full verification.

Phase-one feature development must not begin until the repository initialization commit exists.
