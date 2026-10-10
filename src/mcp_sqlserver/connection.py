import os
import struct
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


# Tipo ODBC do SQL Server para DATETIMEOFFSET (SQL_SS_TIMESTAMPOFFSET).
# O pyodbc nao suporta nativamente esse tipo e falha com
# "ODBC SQL type -155 is not yet supported". Registramos um output converter
# na conexao para decodificar o buffer binario (SQL_SS_TIMESTAMPOFFSET_STRUCT).
_SQL_SS_TIMESTAMPOFFSET = -155


def _converter_timestampoffset(raw):
    """Decodifica o buffer do SQL_SS_TIMESTAMPOFFSET (odbc tipo -155) em uma
    string 'YYYY-MM-DD HH:MM:SS.fffffff +HH:MM'.

    Estrutura de 20 bytes (little-endian):
        SQLSMALLINT  year;             SQLUSMALLINT month, day, hour, minute, second;
        SQLUINTEGER  fraction;         // nanossegundos
        SQLSMALLINT  timezone_hour;    SQLSMALLINT timezone_minute;
    """
    if raw is None:
        return None
    if not isinstance(raw, (bytes, bytearray)) or len(raw) != 20:
        # Layout inesperado: devolve como esta, sem quebrar a consulta.
        return raw
    year, month, day, hour, minute, second, fraction, tz_hour, tz_minute = struct.unpack(
        "<hHHHHHihh", raw
    )
    frac7 = fraction // 100  # nanossegundos -> 100ns (7 digitos)
    sinal = "-" if (tz_hour < 0 or tz_minute < 0) else "+"
    return (
        f"{year:04d}-{month:02d}-{day:02d} {hour:02d}:{minute:02d}:{second:02d}."
        f"{frac7:07d} {sinal}{abs(tz_hour):02d}:{abs(tz_minute):02d}"
    )


def _registrar_converters(conn) -> None:
    """Registra output converters para tipos ODBC nao suportados nativamente
    pelo pyodbc (ex.: datetimeoffset / -155)."""
    try:
        conn.add_output_converter(_SQL_SS_TIMESTAMPOFFSET, _converter_timestampoffset)
    except Exception:
        # Nunca impede a conexao por falha ao registrar o converter.
        pass


def conectar_pyodbc(conn_str: str, timeout: int = None):
    """Abre uma conexao pyodbc, traduzindo erro de driver ODBC ausente em
    uma mensagem clara para o usuario/LLM."""
    try:
        if timeout is None:
            conn = pyodbc.connect(conn_str)
        else:
            conn = pyodbc.connect(conn_str, timeout=timeout)
    except Exception as e:
        if _eh_erro_driver_odbc(str(e)):
            raise RuntimeError(
                "DRIVER ODBC NAO ENCONTRADO: instale o 'ODBC Driver 18 for SQL Server' "
                "e reinicie o servidor (macOS: brew install msodbcsql18). "
                "Erro original: " + str(e)
            ) from e
        raise
    _registrar_converters(conn)
    return conn


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
