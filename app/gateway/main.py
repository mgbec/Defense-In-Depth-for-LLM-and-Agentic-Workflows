"""HTTP API for the LLM security gateway."""

from __future__ import annotations

import hmac
import uuid
from contextlib import asynccontextmanager
from typing import Callable

from fastapi import Depends, FastAPI, Header, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field

from .config import Settings
from .pipeline import GatewayService, ModelError

# Deliberately generic: do not tell a caller which layer rejected them.
BLOCKED_MESSAGE = "Your request could not be processed under our content policy."


class ChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Hard transport-level cap; the pre-filter enforces the (lower) configured limit.
    prompt: str = Field(min_length=1, max_length=20000)


class ChatResponse(BaseModel):
    request_id: str
    blocked: bool
    response: str


def create_app(
    settings: Settings | None = None,
    service_factory: Callable[[Settings], GatewayService] | None = None,
) -> FastAPI:
    state: dict[str, object] = {"service": None, "settings": settings}

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        cfg = state["settings"] or Settings.from_env()
        factory = service_factory
        if factory is None:
            from .factory import build_service  # heavy imports only in the real service

            factory = build_service
        state["settings"] = cfg
        state["service"] = factory(cfg)  # loads models; /healthz stays 503 until done
        yield

    app = FastAPI(
        title="LLM security gateway",
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )

    def authorize(authorization: str | None = Header(default=None)) -> None:
        cfg: Settings = state["settings"]  # type: ignore[assignment]
        expected = f"Bearer {cfg.api_key}"
        if authorization is None or not hmac.compare_digest(authorization, expected):
            raise HTTPException(status_code=401, detail="unauthorized")

    @app.get("/healthz")
    def healthz(response: Response) -> dict[str, str]:
        if state["service"] is None:
            response.status_code = 503
            return {"status": "starting"}
        return {"status": "ok"}

    # Sync endpoint on purpose: scanners are CPU-bound and boto3 is blocking, so FastAPI
    # runs this in its threadpool instead of stalling the event loop.
    @app.post("/v1/chat", response_model=ChatResponse, dependencies=[Depends(authorize)])
    def chat(body: ChatRequest) -> ChatResponse:
        service: GatewayService = state["service"]  # type: ignore[assignment]
        request_id = str(uuid.uuid4())
        try:
            result = service.handle(body.prompt, request_id)
        except ModelError:
            raise HTTPException(status_code=502, detail="upstream model error") from None

        if result.blocked:
            return ChatResponse(request_id=request_id, blocked=True, response=BLOCKED_MESSAGE)
        return ChatResponse(request_id=request_id, blocked=False, response=result.text)

    return app


def app_factory() -> FastAPI:
    """Entry point for uvicorn: ``uvicorn gateway.main:app_factory --factory``."""
    return create_app()
