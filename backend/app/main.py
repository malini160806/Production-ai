import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import db
from .api import routes_core, routes_forecast, routes_planning, routes_reports, routes_scheduling, routes_simulation

app = FastAPI(
    title="AI-Based Production Planning and Scheduling System",
    description="Demand forecasting (XGBoost), production planning, and OR-Tools CP-SAT "
                "production scheduling with disruption simulation.",
    version="1.0.0",
)

DEFAULT_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
EXTRA_ORIGINS = [o.strip() for o in os.environ.get("CORS_ORIGINS", "").split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=DEFAULT_ORIGINS + EXTRA_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    db.init_db()


app.include_router(routes_core.router, prefix="/api")
app.include_router(routes_forecast.router, prefix="/api")
app.include_router(routes_planning.router, prefix="/api")
app.include_router(routes_scheduling.router, prefix="/api")
app.include_router(routes_simulation.router, prefix="/api")
app.include_router(routes_reports.router, prefix="/api")


@app.get("/")
def root():
    return {"message": "AI-Based Production Planning and Scheduling System API. See /docs for OpenAPI UI."}
