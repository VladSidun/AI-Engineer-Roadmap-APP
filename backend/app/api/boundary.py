import re

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.config import Config

LIMIT = 32 * 1024
CHALLENGES = re.compile(r"^/api/v1/exercises/[A-Za-z0-9-]+/challenges$")


def error(status: int, code: str) -> JSONResponse:
    return JSONResponse({"code": code, "message": code, "details": {}}, status_code=status)


class Boundary:
    def __init__(self, app: ASGIApp, config: Config):
        self.app = app
        self.config = config

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        hosts = headers.getlist("host")
        origins = headers.getlist("origin")
        credentials = headers.getlist("authorization")
        method, path = scope["method"], scope["path"]
        scoped = method == "POST" and (
            path == "/api/v1/runner/reports" or CHALLENGES.fullmatch(path)
        )

        async def reject(status: int, code: str) -> None:
            await error(status, code)(scope, receive, send)

        if len(hosts) != 1 or hosts[0] not in self.config.hosts:
            await reject(403, "invalid_host")
            return
        if len(credentials) > 1 or (credentials and not scoped):
            await reject(403, "runner_scope")
            return
        if method not in {"GET", "HEAD", "OPTIONS"}:
            if origins and (len(origins) != 1 or origins[0] not in self.config.origins):
                await reject(403, "invalid_origin")
                return
            if not origins and not scoped:
                await reject(403, "invalid_origin")
                return
            # Buffer only bounded bodies and pass one complete message to FastAPI.
            body = bytearray()
            while True:
                message = await receive()
                if message["type"] == "http.disconnect":
                    return
                body.extend(message.get("body", b""))
                if len(body) > LIMIT:
                    await reject(413, "payload_too_large")
                    return
                if not message.get("more_body"):
                    break

            async def bounded() -> Message:
                return {"type": "http.request", "body": bytes(body), "more_body": False}
        else:
            bounded = receive  # type: ignore[assignment]

        async def secure(message: Message) -> None:
            if message["type"] == "http.response.start":
                h = MutableHeaders(scope=message)
                h["X-Content-Type-Options"] = "nosniff"
                h["Referrer-Policy"] = "no-referrer"
                h["X-Frame-Options"] = "DENY"
                h["Content-Security-Policy"] = (
                    "default-src 'self'; script-src 'self'; style-src 'self'; "
                    "img-src 'self'; object-src 'none'; base-uri 'none'; frame-ancestors 'none'"
                )
                if path.startswith("/api/"):
                    h["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, bounded, secure)
