# AI-Based Production Planning and Scheduling System

An end-to-end manufacturing planning platform: ML demand forecasting (XGBoost),
an explainable production-planning engine, OR-Tools CP-SAT constraint-based
scheduling with a baseline comparison, disruption simulation, and a React
dashboard — all wired to a real FastAPI backend (no mocked dashboard data).

## 1. Architecture

```
backend/                     FastAPI + ML + OR-Tools
  app/
    config.py                 Paths, time conventions, scheduling defaults
    data_access.py             CSV loading + validation (source of truth)
    db.py                       SQLite: schedule runs, audit log, planning approvals, disruption log
    schemas.py                  Pydantic request/response models
    ml/                         Module A — demand forecasting
      features.py                Leakage-safe lag/rolling/calendar features
      train.py                   Chronological train/val/test, XGBoost vs naive baseline
      forecast.py                 Recursive multi-step inference
    planning/                   Module B — production planning
      engine.py                   Net-requirement formula + material/explanation
    scheduling/                  Module C — CP-SAT scheduling + Module F — baseline
      calendar_utils.py            Shift/break/maintenance calendar, working-minute compression
      job_builder.py               DataFrames -> JobSpec
      cp_sat_scheduler.py           OR-Tools CP-SAT model
      baseline_scheduler.py         EDD/FCFS heuristic under identical constraints
      evaluator.py                  Shared metrics + baseline/optimized comparison
      runner.py                     Wires everything together
    simulation/                  Module D — disruption simulation
      disruptions.py                Pure data-transform disruption primitives
      engine.py                     Before/after schedule diff
    api/                          REST endpoints (see §5)
  data/                          CSV source-of-truth (synthetic, clearly labelled)
  models_store/                  Trained per-product XGBoost models + metadata JSON
  scripts/generate_synthetic_data.py
  tests/                         pytest suite (49 tests)

frontend/                    React 19 + TypeScript + Vite + Tailwind v4
  src/
    api/                         Typed REST client
    pages/                        Overview, Forecasting, Planning, Scheduling,
                                   Machines, Simulation, Reports
    components/                   Gantt chart, layout, shared UI primitives
    theme/palette.ts               Validated categorical/status color palette
```

## 2. Setup

### Prerequisites
- Python 3.12+
- Node.js 20+

### Backend

```bash
cd backend
python -m venv venv
./venv/Scripts/activate        # Windows (PowerShell: .\venv\Scripts\Activate.ps1)
# source venv/bin/activate      # macOS/Linux
pip install -r requirements.txt

# Generate synthetic data (skips any files that already exist — never overwrites real data)
python scripts/generate_synthetic_data.py

# Run tests
pytest tests/ -q

# Start the API
uvicorn app.main:app --reload --port 8000
```

API docs (OpenAPI/Swagger): http://localhost:8000/docs

### Frontend

```bash
cd frontend
npm install
cp .env.example .env     # defaults to http://localhost:8000/api
npm run dev
```

Open http://localhost:5173. The backend must be running first — every page
fetches real data from the API; nothing is hardcoded.

### First run

1. Start the backend (generates and validates synthetic data automatically if you ran the generator).
2. On the **Demand Forecasting** page, click **Train / Evaluate Model** for a product (or call
   `POST /api/forecast/train` with no body to train all products at once).
3. Visit **Production Planning** → Generate Recommendations.
4. Visit **Production Scheduling** → Optimize Schedule.
5. Try a disruption on **Scenario Simulation** or **Machine Management**.

## 3. Data

All CSVs under `backend/data/` are **synthetic** (see `SYNTHETIC_DATA_NOTICE.txt`,
written by the generator) — six products, five machines, ~6 months of daily
demand history, confirmed/pending orders, inventory, a small bill of
materials, raw-material stock, and a couple of maintenance windows. The
generator (`backend/scripts/generate_synthetic_data.py`) **never overwrites
existing files** unless `--force` is passed, so dropping in real CSVs with
the same filenames and schema is safe — the data layer only cares about
column names and types (see `REQUIRED_COLUMNS` in `data_access.py`).

## 4. Key design decisions & assumptions (read before extending)

- **Time units.** All schedule timestamps are integer minutes. Internally, the
  CP-SAT/baseline schedulers work in **compressed working minutes** — a shared
  calendar (shift start/end minus the lunch break, see `config.py`) is used to
  strip out nights and breaks, so a job's duration is never charged against
  non-working time and can legitimately span multiple shifts/days (pausing
  overnight, resuming the next shift) instead of being forced into one
  contiguous window. Per-machine maintenance/breakdown windows are layered on
  top as extra obstacles specific to that machine. `WorkTimeMapping.work_to_calendar`
  converts back to real timestamps for display. This was a deliberate fix after
  an initial version blocked any job longer than a half-shift window entirely —
  see the git history / code comments in `calendar_utils.py` for the full rationale.
- **Setup time** is charged in full per job; there is no sequence-dependent
  setup-time reduction (e.g., running the same product back-to-back doesn't
  save setup minutes). This is a documented simplification, not a bug.
- **Demand forecast vs. confirmed orders** (Module B): `expected_demand =
  max(confirmed_order_qty, forecast_qty)`, not their sum — a forecast is meant
  to approximate total demand including what becomes confirmed orders, so
  summing them would double-count. See `planning/engine.py` docstring.
- **Material readiness** (Module C): raw material stock is allocated to orders
  in due-date order; an order whose requirement exceeds remaining stock is
  pushed back by the product's `lead_time_days` (used as a replenishment-time
  proxy) rather than silently scheduled against insufficient stock.
- **Infeasible orders are reported, never forced.** Each order may go
  unscheduled with an explicit reason (no compatible machine, no slot within
  the horizon, etc.) rather than being assigned an impossible slot. The CP-SAT
  objective includes a very large penalty for leaving an order unscheduled, so
  this only happens when scheduling it is truly impossible or pointless.
- **Solver determinism.** CP-SAT runs single-threaded with a fixed random seed
  so identical input always produces identical output — important for Module D,
  where a "before" and "after" schedule are diffed and every difference should
  be attributable to the simulated disruption, not to parallel-search race
  noise. This is a real limitation worth knowing: the optimizer **does not**
  minimize deviation from the previous schedule (no schedule-stability
  objective), so a disruption can shift jobs that aren't directly affected by
  it, as long as doing so improves the objective. Two consecutive runs on
  unchanged input will always agree, but "what changed" in the simulation diff
  can include incidental re-optimization, not only changes causally required
  by the disruption. A stability term (penalize deviation from a reference
  schedule) would be the natural next step.
- **Status is never fabricated.** The scheduler reports `OPTIMAL`, `FEASIBLE`,
  `INFEASIBLE`, or `UNKNOWN` exactly as returned by CP-SAT — `FEASIBLE` means
  the solver found a valid schedule but did not prove it optimal within the
  time limit; this is shown as-is in the UI, not rounded up to "optimal."
  Forecast accuracy and schedule/baseline comparisons are always computed from
  a real run (chronological test split; two schedules solved over identical
  orders/machines/constraints) — never asserted.
- **No fabricated predictive maintenance.** Per the project brief, there is no
  machine-failure classifier trained on arbitrary synthetic labels. Breakdowns
  in Module D are user-simulated events, not predictions.
- **Precedence constraints** (multi-stage routing) are supported in the solver
  (`precedence_pairs` argument) but unused by default because the synthetic
  BOM/processing data has no multi-stage routes — wiring real multi-stage data
  in is a matter of passing those pairs through `job_builder`/`runner`.

## 5. REST API

All endpoints are under `/api`. Full interactive docs at `/docs`.

| Endpoint | Method | Purpose |
|---|---|---|
| `/health` | GET | Data-source validation status |
| `/products`, `/machines`, `/orders` | GET | Master data |
| `/processing-times`, `/machine-status` | GET | Supporting reads for the Machines page |
| `/forecast/train` | POST | Train/evaluate XGBoost model(s) |
| `/forecast` | POST | Recursive N-day forecast for one product |
| `/planning/generate` | POST | Net-requirement recommendations for all/selected products |
| `/planning/approve` | POST | Approve/reject a recommendation (persisted) |
| `/planning/approvals` | GET | Approval history |
| `/schedule/optimize` | POST | CP-SAT schedule + baseline comparison, optionally persisted |
| `/schedule/reschedule` | POST | Re-solve from current data, respecting locked/committed jobs |
| `/schedule/runs` | GET | Schedule run history (audit trail) |
| `/simulation/run` | POST | Apply one disruption, diff before/after schedule |
| `/metrics` | GET | Dashboard overview metrics |
| `/reports` | GET | Forecast + schedule + baseline-comparison report |

## 6. Testing

```bash
cd backend
pytest tests/ -q
```

49 tests covering: data validation, feature-engineering leakage prevention,
model training/chronological evaluation, machine compatibility, no-overlap,
tardiness/due-date math, infeasible-order detection, maintenance/shift
constraints, locked-job preservation, planning formula (incl. the
double-counting guard and material constraint), disruption simulation, and
API request validation/error handling.

Frontend: `npm run build` runs `tsc -b` (strict type-check) then `vite build`.

## 7. Known limitations

- No schedule-stability objective in Module D (see above) — disruption diffs
  can include re-optimization unrelated to the disruption itself.
- Setup time is not sequence-dependent.
- Single shared shift calendar across machines; per-machine shift differences
  would require extending `job_builder`/`calendar_utils` to build a mapping
  per machine instead of one shared mapping (maintenance is already per-machine).
- The frontend's browser-based visual QA for this build was done via
  TypeScript strict-mode compilation, a full production `vite build`, and
  direct API-contract verification (every response shape checked against the
  TypeScript types) rather than an interactive browser session — no Chrome
  automation tool was available in this environment. Recommend a manual
  click-through before relying on it for a demo.
