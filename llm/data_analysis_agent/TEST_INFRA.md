# Test Infrastructure Architecture: WPS-AI Data Analysis Studio Expansion

This document defines the architecture, feature inventory, testing methodology, coverage thresholds, and verification standards for the **WPS-AI Visual-First Diagnostic Engine & Interactive Scenario What-If Studio**.

---

## 1. Executive Summary & Quality Strategy

The WPS-AI Expansion introduces high-performance, model-free visual diagnostics and real-time counterfactual scenario simulation. In accordance with the Project Constitution (`GEMINI.md`), the architecture guarantees:
1. **Zero Backend Plotting Bloat**: 100% of visual charts emit native Apache ECharts JSON specifications (`ChartSpec.option`) with zero backend plotting dependencies (`matplotlib`, `seaborn`, `plotly` are strictly prohibited).
2. **Sub-100ms Latency Budget**: Interactive slider simulation and surrogate evaluations run in $<1\text{ms}$ in-memory via closed-form Ridge projections and regularized covariance matrices.
3. **Air-Gap Integrity**: Zero external HTTP calls during analysis, profiling, diagnostics, or simulation.
4. **Fail Explicitly & Early**: Strict domain exception hierarchy rooted in `WPSAIBaseException`.

The end-to-end testing suite implements a **4-tier opaque-box test architecture** that exercises the complete system from public contracts down to mathematical conservation and sub-second performance bounds.

---

## 2. Feature Inventory (F1 – F11)

| Feature ID | Name | Module Touchpoint | Primary Capability | Public Contract |
|---|---|---|---|---|
| **F1** | Subgroup Slice Isolation | `pipeline_core/statistics/anomaly_spotlight.py` | Multi-predicate Beam Search to isolate anomalous cohorts driving metric drops | `AnomalySpotlight.isolate_slices()` |
| **F2** | Shift Attribution Waterfall | `pipeline_core/statistics/blame_bridge.py` | Oaxaca-Blinder / Rate-Mix & linear surrogate waterfall with exact conservation | `BlameBridge.attribute_shift()` |
| **F3** | Domino Timeline | `pipeline_core/statistics/domino_timeline.py` | PELT changepoint detection & lead-lag cross-correlation ordering metrics from $T=0$ | `DominoTimeline.detect_cascade()` |
| **F4** | Portable Statistics Package | `pipeline_core/statistics/__init__.py` | Package re-exporting `forecast` and diagnostic primitives with backward compatibility | `pipeline_core.statistics` |
| **F5** | Domain Exceptions Hierarchy | `backend/exceptions.py` | Precise custom exceptions inheriting from `WPSAIBaseException` | `DiagnosticEngineError`, `ScenarioSimulationError` |
| **F6** | Jargon-to-Visual Translator | `backend/services/jargon_translator.py` | Deterministic mapping of $p$-values, $R^2$, $D_M$ to Confidence Badges & 3-layer charts | `JargonTranslator` |
| **F7** | Agent Service Streaming | `backend/services/agent_service.py` | Streaming pipeline with self-correction, confidence badges, and follow-up chips | `AgentService.run_analysis_stream()` |
| **F8** | What-If Studio Engine | `backend/services/whatif_service.py` | Feature roles, closed-form Ridge surrogate, Mahalanobis OOD, 3 recipe cards, weather fan | `WhatIfService` / `ScenarioSimulator` |
| **F9** | SessionStore Surrogate Cache | `backend/services/session_store.py` & API | In-memory surrogate caching in `SessionStore` & fast REST endpoints (`/scenario/predict`) | `SessionStore` & Scenario Router |
| **F10** | Frontend Diagnostics Contract | `frontend/src/components/` & ECharts | ECharts JSON specifications, color palette `#ef4444` / `#94a3b8` / `#10b981`, 3-layer rule | `ChartSpec.option` validation |
| **F11** | Frontend Scenario Controls Contract | `frontend/src/components/ScenarioStudio/` | 3-zone slider tracks (Green/Amber/Red striped), Reality Check banner, Recipe Cards | Slider tracks & OOD schema |

---

## 3. 4-Tier Test Architecture & Methodology

```
┌────────────────────────────────────────────────────────────────────────┐
│                        TIER 4: REAL-WORLD SCENARIOS                    │
│   E-Commerce Checkout Drop | SaaS Latency Cascade | Retail Margin Opt  │
├────────────────────────────────────────────────────────────────────────┤
│                   TIER 3: CROSS-FEATURE PAIRWISE INTERACTIONS          │
│   Spotlight + Badges | Domino + Waterfall | Sliders + Reality Check    │
├────────────────────────────────────────────────────────────────────────┤
│                   TIER 2: BOUNDARY & CORNER CASES (>=5 / feature)      │
│   Zero Variance | Singular Covariance | Collinearity | Extreme OOD     │
├────────────────────────────────────────────────────────────────────────┤
│                   TIER 1: FEATURE COVERAGE (>=5 / feature)             │
│   Happy-Path & Public Contract Validation for Features F1 .. F11      │
└────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Tier 1: Feature Coverage (Happy Path & Public Contracts)
- **Methodology**: Category-Partition testing over nominal input domains.
- **Coverage Requirement**: $\ge 5$ distinct test cases per feature across F1 through F11 ($\ge 55$ test cases total).
- **Verification Focus**:
  - Exact return dictionary structure matching published specifications.
  - Correct mathematical properties (e.g., Welch's $t$-statistic significance, exact waterfall conservation $\bar{Y}_0 + \sum \Delta = \bar{Y}_1$, changepoint timestamps).
  - Valid Apache ECharts option trees adhering to semantic styling.

### 3.2 Tier 2: Boundary Value Analysis & Corner Cases
- **Methodology**: Boundary Value Analysis (BVA), extreme value testing, and fault injection.
- **Coverage Requirement**: $\ge 5$ distinct boundary/corner cases per feature across F1 through F11 ($\ge 55$ test cases total).
- **Verification Focus**:
  - Zero metric variance across subgroups (handling flatlines).
  - Minimal sample sizes ($N < 5$, $N < 15$, $N < 30$).
  - High-cardinality ID column filtering ($>1000$ unique values excluded from slice predicates).
  - Perfect multicollinearity between levers leading to singular covariance matrices (Ridge regularization $\Sigma + \epsilon I$).
  - Extreme out-of-distribution (OOD) slider inputs ($10\times$ historical maximum).
  - Unreachable counterfactual targets (exceeding physical/bounded slider limits).
  - Zero net shift between periods ($\Delta Y = 0$).
  - Simultaneous metric breakdown (tie-breaking in Domino Timeline).

### 3.3 Tier 3: Cross-Feature Interactions (Pairwise Combinatorial)
- **Methodology**: Pairwise combinatorial testing verifying interface handoffs and data flow across subsystems.
- **Coverage Requirement**: $\ge 10$ cross-feature interaction scenarios.
- **Verification Focus**:
  - **F1 + F6**: Anomaly Spotlight slice metrics seamlessly feed into Jargon Translator to produce 3-layer charts and confidence badges.
  - **F3 + F2**: Domino Timeline identifies root breakdown metric at $T=0$, which directly triggers Blame Bridge shift attribution on that specific metric.
  - **F8 + F9 + F11**: Slider dragging checks Mahalanobis distance in SessionStore cache, triggers Reality Check banner, and requests 3 counterfactual recipe cards.
  - **F1 + F8**: Culprit subgroup identified by Anomaly Spotlight initiates a targeted scenario simulation to model recovery of that subgroup.
  - **F7 + F9**: Agent Service chat stream formats interactive what-if parameters backed by pre-warmed SessionStore surrogate cache.
  - **F3 + F6**: Domino Timeline sparklines pass through 3-Layer Rule Enforcer with synchronized markLine event pin.
  - **F2 + F8**: Negative drivers from Blame Bridge waterfall populate candidate levers in What-If Studio.
  - **F4 + Security**: `pipeline_core/statistics` runs in complete isolation with 0 backend imports and 0 network socket bindings.
  - **F9 + Session**: Dataset updates invalidate existing surrogate cache entries in `SessionStore`.
  - **Full Triad Pipeline**: Anomaly Spotlight -> Blame Bridge -> Domino Timeline end-to-end execution on a shared session.

### 3.4 Tier 4: Real-World Workload Scenarios
- **Methodology**: Representative end-to-end production workloads simulating real enterprise data incidents.
- **Coverage Requirement**: $\ge 4$ complete real-world scenarios.
- **Verification Focus**:
  1. **E-Commerce Checkout Drop**: 10,000 checkout records; Friday afternoon conversion drop of 4.2%; Beam search isolates `Device=iOS AND Payment=ApplePay`; Waterfall attributes gateway decline; Domino timeline reveals `gateway_latency_ms` broke at $T=0$; What-If Studio models backup gateway recovery.
  2. **Enterprise SaaS API Latency Cascade**: Multi-service microservice telemetry; Database connection pool exhaustion at $T=0$ cascades to API gateway 504 errors; Jargon translator maps kurtosis and heteroskedasticity; What-If Studio tests pool scaling slider with weather range forecast ($P_{10}$–$P_{90}$).
  3. **Retail Revenue Margin Optimization**: Multi-store retail dataset with 5 controllable levers (`Discount_Pct`, `Ad_Spend`, `Inventory_Depth`, `Staffing_Hours`, `Shipping_SLA`); Controllable levers separated from locked immutable context; Mahalanobis distance flags $D_M > \chi_p^2(0.99)$ for contradictory slider combinations; 3 Recipe Cards generated to achieve target margin; Monte Carlo goal speedometer evaluated.
  4. **Subscription SaaS Churn Spike**: Enterprise SaaS subscription cohort dataset; Identifies enterprise tier churn spike; Oaxaca decomposition isolates plan price change vs support response time; Counterfactual solver generates 3 actionable retention recipes.

---

## 4. Coverage Thresholds & Quality Gates

| Metric | Target Threshold | Enforcement Mechanism |
|---|---|---|
| **Tier 1 Feature Tests** | $\ge 55$ tests ($\ge 5$ per feature F1..F11) | Automated `pytest` suite |
| **Tier 2 Boundary Tests** | $\ge 55$ tests ($\ge 5$ per feature F1..F11) | Automated `pytest` suite |
| **Tier 3 Interaction Tests** | $\ge 10$ pairwise test cases | Automated `pytest` suite |
| **Tier 4 Scenario Tests** | $\ge 4$ real-world workloads | Automated `pytest` suite |
| **Total Test Cases** | $\ge 124$ tests | Automated `pytest` suite |
| **Surrogate Prediction Latency** | $<100\text{ms}$ budget (typical $<5\text{ms}$) | Asserted in tests via `time.perf_counter` |
| **Waterfall Conservation** | Exact float conservation ($\pm 10^{-6}$) | Mathematical equality assertion |
| **Zero Backend Plotting Bloat** | 0 occurrences of `matplotlib`, `seaborn`, `plotly` | Ast-based import audit test |
| **Air-Gap Guarantee** | 0 external network calls | Socket-blocking test fixture |
| **Static Typing** | 0 errors under `mypy --strict` | Static type check gate |

---

## 5. Test Suite Execution & Runner Instructions

The test suite is located in `tests/test_e2e_expansion.py` and can be executed via `uv`:

```bash
# Run the complete 4-tier E2E expansion suite
uv run pytest tests/test_e2e_expansion.py -v

# Run by Tier
uv run pytest tests/test_e2e_expansion.py -k "TestTier1" -v
uv run pytest tests/test_e2e_expansion.py -k "TestTier2" -v
uv run pytest tests/test_e2e_expansion.py -k "TestTier3" -v
uv run pytest tests/test_e2e_expansion.py -k "TestTier4" -v

# Run with latency benchmark logging
uv run pytest tests/test_e2e_expansion.py -s -k "latency"
```
