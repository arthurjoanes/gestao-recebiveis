from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from gestao_recebiveis.import_csv import MAX_BYTES

MAX_REQUEST_BYTES = MAX_BYTES + 64 * 1024
MAX_JSON_BYTES = 8 * 1024


class RequestBodyLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if (
            scope["type"] != "http"
            or scope["method"] not in {"POST", "PUT", "PATCH"}
            or not scope["path"].startswith("/api/v1/")
        ):
            await self.app(scope, receive, send)
            return
        headers = dict(scope["headers"])
        is_upload = scope["path"].rstrip("/") == "/api/v1/imports"
        limit = MAX_REQUEST_BYTES if is_upload else MAX_JSON_BYTES
        try:
            declared = int(headers.get(b"content-length", b"0"))
        except ValueError:
            declared = limit + 1
        if declared < 0 or declared > limit:
            await self.reject(scope, receive, send, is_upload)
            return
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            body.extend(message.get("body", b""))
            if len(body) > limit:
                await self.reject(scope, receive, send, is_upload)
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)

    @staticmethod
    async def reject(scope: Scope, receive: Receive, send: Send, is_upload: bool) -> None:
        response = JSONResponse(
            status_code=413,
            content={
                "code": "file_too_large" if is_upload else "request_too_large",
                "message": (
                    "Arquivo maior que 2 MiB ou formulário multipart excessivo."
                    if is_upload
                    else "Requisição maior que 8 KiB."
                ),
            },
        )
        await response(scope, receive, send)
