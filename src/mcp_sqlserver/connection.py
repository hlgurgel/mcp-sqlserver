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


def connection_string_configurada() -> bool:
    """Indica se a string de conexao esta configurada, sem levantar excecao."""
    return bool(_CONNECTION_STRING)


_PADROES_ERRO_DRIVER = [
    "can't open lib",
    "file not found",
    "data source name not found",
    "no default driver",
    "im002",
    "sqlallochandle",
]


def _eh_erro_driver_odbc(mensagem: str) -> bool:
    m = mensagem.lower()
    return any(padrao in m for padrao in _PADROES_ERRO_DRIVER)


def conectar_pyodbc(conn_str: str, timeout: int = None):
    """Abre uma conexao pyodbc, traduzindo erro de driver ODBC ausente em
    uma mensagem clara para o usuario/LLM."""
    try:
        if timeout is None:
            return pyodbc.connect(conn_str)
        return pyodbc.connect(conn_str, timeout=timeout)
    except Exception as e:
        if _eh_erro_driver_odbc(str(e)):
            raise RuntimeError(
                "DRIVER ODBC NAO ENCONTRADO: instale o 'ODBC Driver 18 for SQL Server' "
                "e reinicie o servidor (macOS: brew install msodbcsql18). "
                "Erro original: " + str(e)
            ) from e
        raise


def get_connection():
    global _CONNECTION
    conn_str = get_connection_string()
    if _CONNECTION is not None:
        try:
            cursor = _CONNECTION.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
            return _CONNECTION
        except Exception:
            try:
                _CONNECTION.close()
            except Exception:
                pass
            _CONNECTION = None
    if _CONNECTION is None:
        _CONNECTION = conectar_pyodbc(conn_str)
        _CONNECTION.autocommit = False
        cursor = _CONNECTION.cursor()
        cursor.execute("SET XACT_ABORT ON")
        cursor.close()
    return _CONNECTION


def close_connection():
    global _CONNECTION
    if _CONNECTION is not None:
        _CONNECTION.close()
        _CONNECTION = None


_PERMISSAO_ESCRITA_CACHE = None


def usuario_tem_permissao_escrita() -> bool:
    """Detecta se o usuario da conexao tem permissao de escrita no SQL Server.

    Verifica roles de escrita no nivel do servidor (sysadmin) e no banco
    padrao da conexao (db_owner, db_datawriter, db_ddladmin).

    Fail-safe: se a deteccao falhar por qualquer motivo (banco inacessivel,
    timeout, sem permissao ate para consultar roles), assume somente leitura
    (retorna False), nunca expondo ferramentas de escrita por engano.

    O resultado e cacheado na primeira chamada.
    """
    global _PERMISSAO_ESCRITA_CACHE
    if _PERMISSAO_ESCRITA_CACHE is not None:
        return _PERMISSAO_ESCRITA_CACHE

    _PERMISSAO_ESCRITA_CACHE = False
    try:
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT "
                "CAST(IS_SRVROLEMEMBER('sysadmin') AS BIT), "
                "CAST(IS_MEMBER('db_owner') AS BIT), "
                "CAST(IS_MEMBER('db_datawriter') AS BIT), "
                "CAST(IS_MEMBER('db_ddladmin') AS BIT)"
            )
            row = cursor.fetchone()
            if row:
                _PERMISSAO_ESCRITA_CACHE = any(bool(v) for v in row)
        finally:
            cursor.close()
    except Exception:
        _PERMISSAO_ESCRITA_CACHE = False

    return _PERMISSAO_ESCRITA_CACHE
