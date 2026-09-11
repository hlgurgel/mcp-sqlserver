"""Servidor HTTP (Streamable HTTP) do mcp-sqlserver.

Expoe as ferramentas do mcp-sqlserver via HTTP no endpoint ``/mcp``, usando o
transporte Streamable HTTP do MCP (o padrao moderno, substituindo o SSE).

Requer o extra ``server`` (uvicorn + starlette):

    pip install 'sqlserver-mcp-tools[server]'

Variaveis de ambiente opcionais:

- ``MCP_HOST``: host de escuta (padrao ``0.0.0.0``)
- ``MCP_PORT``: porta de escuta (padrao ``8090``)
"""

import os

from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

from .server import servidor


class _StreamableHTTPASGIApp:
    """Wrapper ASGI para o handler do session manager.

    O Starlette trata funcao/metodo como ``func(request)`` (default GET), mas
    classe/instancia como ASGI app puro — necessario para o Streamable HTTP
    aceitar POST/DELETE.
    """

    def __init__(self, session_manager: StreamableHTTPSessionManager):
        self.session_manager = session_manager

    async def __call__(self, scope, receive, send) -> None:
        await self.session_manager.handle_request(scope, receive, send)


class _HealthCheckMiddleware:
    """Responde 200 OK a um GET simples no /mcp (sem Accept text/event-stream).

    Clientes como o Claude Desktop validam a URL com um GET simples (como um
    navegador). O transport Streamable HTTP rejeita esse GET com 406, fazendo o
    cliente concluir que "nenhum servidor respondeu". Este middleware intercepta
    esses GETs e devolve um health check JSON, deixando passar apenas GETs que
    de fato querem abrir um stream SSE (Accept: text/event-stream).
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] == "http"
            and scope["method"] == "GET"
            and scope["path"] == "/mcp"
        ):
            headers = {k.decode().lower(): v.decode() for k, v in scope["headers"]}
            accept = headers.get("accept", "")
            if "text/event-stream" not in accept:
                body = b'{"status":"ok"}'
                await send({
                    "type": "http.response.start",
                    "status": 200,
                    "headers": [[b"content-type", b"application/json"]],
                })
                await send({"type": "http.response.body", "body": body})
                return
        await self.app(scope, receive, send)


def criar_app():
    """Monta a aplicacao Starlette com o transporte Streamable HTTP em /mcp."""
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.routing import Route

    session_manager = StreamableHTTPSessionManager(app=servidor, json_response=True)

    return Starlette(
        routes=[Route("/mcp", endpoint=_StreamableHTTPASGIApp(session_manager))],
        middleware=[Middleware(_HealthCheckMiddleware)],
        lifespan=lambda app: session_manager.run(),
    )


def main():
    try:
        import uvicorn
    except ImportError as e:
        raise SystemExit(
            "O modo HTTP requer o extra 'server'. Instale com: "
            "pip install 'sqlserver-mcp-tools[server]'"
        ) from e

    host = os.getenv("MCP_HOST", "0.0.0.0")
    port = int(os.getenv("MCP_PORT", "8090"))
    uvicorn.run(criar_app(), host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
