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


def criar_app():
    """Monta a aplicacao Starlette com o transporte Streamable HTTP em /mcp."""
    from starlette.applications import Starlette
    from starlette.routing import Route

    session_manager = StreamableHTTPSessionManager(app=servidor)

    return Starlette(
        routes=[Route("/mcp", endpoint=_StreamableHTTPASGIApp(session_manager))],
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
