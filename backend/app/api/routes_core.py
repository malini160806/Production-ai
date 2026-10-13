import pandas as pd
from fastapi import APIRouter, HTTPException

from .. import data_access as da
from ..data_access import DataValidationError
from ..schemas import HealthResponse, MachineOut, OrderOut, ProductOut

router = APIRouter(tags=["core"])


@router.get("/health", response_model=HealthResponse)
def health():
    summary = da.data_health_summary()
    overall_ok = all(v["ok"] for v in summary.values())
    return HealthResponse(status="ok" if overall_ok else "degraded", data_sources=summary)


@router.get("/products", response_model=list[ProductOut])
def get_products():
    try:
        df = da.load_products()
    except DataValidationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return df.to_dict(orient="records")


@router.get("/machines", response_model=list[MachineOut])
def get_machines():
    try:
        df = da.load_machines()
    except DataValidationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return df.to_dict(orient="records")


@router.get("/processing-times")
def get_processing_times():
    try:
        df = da.load_processing_times()
    except DataValidationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return df.to_dict(orient="records")


@router.get("/machine-status")
def get_machine_status():
    try:
        df = da.load_machine_status()
    except DataValidationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    return df.to_dict(orient="records")


@router.get("/orders", response_model=list[OrderOut])
def get_orders():
    try:
        df = da.load_orders()
    except DataValidationError as e:
        raise HTTPException(status_code=500, detail=str(e))
    records = df.to_dict(orient="records")
    for r in records:
        val = r.get("committed_machine_id")
        r["committed_machine_id"] = None if (val is None or (isinstance(val, float) and pd.isna(val))) else str(val)
    return records
