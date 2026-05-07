import os
from pathlib import Path
import pyodbc
from dotenv import load_dotenv

_RAIZ_MCP = Path(__file__).resolve().parent.parent.parent

# Se MSSQL_ENV_FILE estiver definida, carrega o arquivo indicado
_env_explicito = os.getenv("MSSQL_ENV_FILE", "")
if _env_explicito:
    _caminho_explicito = Path(_env_explicito)
    if _caminho_explicito.exists():
        load_dotenv(_caminho_explicito, override=True)

# Caminhos automaticos (CWD e raiz do MCP)
_caminhos_env = [
    _RAIZ_MCP / ".env",          # menor prioridade (fallback)
    Path.cwd() / ".." / ".env",  # prioridade media
    Path.cwd() / ".env",         # maior prioridade (CWD)
]
for _caminho in _caminhos_env:
    if _caminho.exists():
        load_dotenv(_caminho, override=True)

_CONNECTION_STRING = os.getenv("MSSQL_CONNECTION_STRING", "")
_CONNECTION = None


def get_connection_string() -> str:
    if not _CONNECTION_STRING:
        raise ValueError(
            "MSSQL_CONNECTION_STRING nao definida. "
            "Configure a variavel de ambiente ou crie um arquivo .env "
            "baseado no .env.example."
        )
    return _CONNECTION_STRING


def get_connection():
    global _CONNECTION
    if _CONNECTION is None:
        conn_str = get_connection_string()
        _CONNECTION = pyodbc.connect(conn_str)
    return _CONNECTION


def close_connection():
    global _CONNECTION
    if _CONNECTION is not None:
        _CONNECTION.close()
        _CONNECTION = None
