"""FastAPI application entry point."""

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from validation_pipeline.api.routes import router
from validation_pipeline.config import settings
from validation_pipeline.schemas.validation_run import FieldError, ValidationErrorResponse

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

app = FastAPI(
    title="Idea Validation Pipeline",
    version="0.1.0",
    description="AI-assisted idea validation pipeline API",
)


@app.exception_handler(ValidationError)
async def pydantic_validation_handler(request: Request, exc: ValidationError):
    """FR-4, FR-5: Return field-level validation errors."""
    errors = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err["loc"])
        errors.append(FieldError(field=field, message=err["msg"]))
    body = ValidationErrorResponse(errors=errors)
    return JSONResponse(status_code=400, content=body.model_dump())


app.include_router(router)


@app.get("/health")
async def health():
    return {"status": "ok"}
