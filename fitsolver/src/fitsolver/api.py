"""HTTP surface. Deliberately thin: parse, call engine, return.

Run:  uvicorn fitsolver.api:app --port 8000
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request

from . import io
from .engine import solve

app = FastAPI(title="FitSolver", version=io.SOLVER_VERSION)


@app.get("/v1/health")
def health() -> dict:
    return {"status": "ok", "solver_version": io.SOLVER_VERSION,
            "schema_version": io.SCHEMA_VERSION}


@app.post("/v1/solve")
async def solve_endpoint(request: Request) -> dict:
    try:
        payload = await request.json()
    except ValueError as e:
        raise HTTPException(status_code=400,
                            detail="request body is not valid JSON") from e
    try:
        return solve(payload)
    except io.RequestError as e:
        raise HTTPException(status_code=422, detail=str(e)) from e
