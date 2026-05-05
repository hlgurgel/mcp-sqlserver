import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

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
