from datetime import date

from fastapi import APIRouter, HTTPException

from .. import data_access as da
from .. import db
from ..data_access import DataValidationError
from ..simulation.engine import UnknownDisruptionType, run_simulation
from ..schemas import SimulationRequest

router = APIRouter(prefix="/simulation", tags=["simulation"])


@router.post("/run")
def run(req: SimulationRequest):
    try:
        data = {
            "orders": da.load_orders(),
            "machines": da.load_machines(),
            "processing_times": da.load_processing_times(),
            "machine_status": da.load_machine_status(),
            "bill_of_materials": da.load_bom(),
            "raw_materials": da.load_raw_materials(),
            "products": da.load_products(),
        }
    except DataValidationError as e:
        raise HTTPException(status_code=500, detail=str(e))

    weights = req.objective_weights.model_dump() if req.objective_weights else None
    try:
        result = run_simulation(
            req.disruption_type, req.params, data, date.today(), req.horizon_days, weights,
            req.time_limit_seconds,
        )
    except UnknownDisruptionType as e:
        raise HTTPException(status_code=400, detail=str(e))
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing required parameter: {e}")

    db.log_disruption_event(req.disruption_type, req.params, result["description"])
    db.log_audit("disruption_simulated", {"disruption_type": req.disruption_type, "params": req.params})
    return result
