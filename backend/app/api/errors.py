from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.solvers.base import InfeasibleError
from app.validation import InvariantError


def register_handlers(app: FastAPI) -> None:
    "Register exception and map HTTP response"

    @app.exception_handler(InfeasibleError)
    async def _infeasible(request: Request, exc: InfeasibleError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"error": "infeasible", "why": exc.reasons},
        )

    @app.exception_handler(InvariantError)
    async def _invariant(request: Request, exc: InvariantError) -> JSONResponse:
        # If here, the solver produced a bad schedule.
        return JSONResponse(
            status_code=500,
            content={
                "error": "solver_invariant_violation",
                "detail": str(exc),
            },
        )

    @app.exception_handler(ValueError)
    async def _value_error(request: Request, exc: ValueError) -> JSONResponse:
        # Currently used for unknown objective_mode from the objectives registry.
        return JSONResponse(
            status_code=400,
            content={"error": "bad_request", "detail": str(exc)},
        )
