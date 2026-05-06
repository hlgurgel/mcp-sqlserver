import json
from .connection import get_connection, get_connection_string

MAX_ROWS = 2000

_BANCO_PADRAO = "master"
_conn_str = get_connection_string()
for _parte in _conn_str.split(";"):
    if _parte.strip().upper().startswith("DATABASE="):
        _BANCO_PADRAO = _parte.split("=", 1)[1].strip()
        break


def _definir_banco(cursor, banco=None):
    banco_alvo = banco if banco else _BANCO_PADRAO
    cursor.execute(f"USE [{banco_alvo}]")


def _format_resultado(cursor) -> str:
    colunas = [col[0] for col in cursor.description] if cursor.description else []
    linhas = [dict(zip(colunas, row)) for row in cursor.fetchmany(MAX_ROWS)]
    return json.dumps(linhas, default=str, ensure_ascii=False, indent=2)


def listar_bancos() -> str:
    """Lista todos os bancos de dados acessiveis no servidor."""
    sql = """
        SELECT name, state_desc, create_date, compatibility_level
        FROM sys.databases
        ORDER BY name
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        return _format_resultado(cursor)
    except Exception as e:
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()


def consulta(sql: str) -> str:
    """Executa uma consulta SELECT (somente leitura).

    Use notacao de tres niveis para acessar outros bancos:
    banco.esquema.tabela

    Args:
        sql: Query SQL do tipo SELECT.
    """
    sql_upper = sql.strip().upper()
    palavras_proibidas = [
        "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER",
        "CREATE", "EXEC", "EXECUTE", "MERGE", "GRANT", "REVOKE",
        "BACKUP", "RESTORE", "DBCC",
    ]
    for palavra in palavras_proibidas:
        if sql_upper.startswith(palavra) or f"\n{palavra}" in sql_upper:
            return f"OPERACAO BLOQUEADA: '{palavra}' nao permitido. Apenas SELECT."

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        return _format_resultado(cursor)
    except Exception as e:
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()


def listar_tabelas(banco: str = "") -> str:
    """Lista todas as tabelas e views do banco de dados.

    Args:
        banco: Nome do banco de dados (opcional). Se nao informado,
               usa o banco padrao da conexao.
    """
    sql = """
        SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_TYPE
        FROM INFORMATION_SCHEMA.TABLES
        ORDER BY TABLE_SCHEMA, TABLE_NAME
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _definir_banco(cursor, banco)
        cursor.execute(sql)
        return _format_resultado(cursor)
    except Exception as e:
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()


def descrever_tabela(tabela: str, banco: str = "") -> str:
    """Descreve a estrutura de uma tabela: colunas, tipos, nulabilidade e chaves.

    Args:
        tabela: Nome da tabela. Use 'schema.nome' ou apenas 'nome' (default: dbo).
        banco: Nome do banco de dados (opcional).
    """
    schema = "dbo"
    nome_tabela = tabela
    if "." in tabela:
        schema, nome_tabela = tabela.split(".", 1)

    sql = """
        SELECT
            c.COLUMN_NAME,
            c.DATA_TYPE,
            c.CHARACTER_MAXIMUM_LENGTH,
            c.IS_NULLABLE,
            c.COLUMN_DEFAULT,
            CASE WHEN pk.COLUMN_NAME IS NOT NULL THEN 'PK' ELSE '' END AS CHAVE_PRIMARIA
        FROM INFORMATION_SCHEMA.COLUMNS c
        LEFT JOIN (
            SELECT ku.TABLE_SCHEMA, ku.TABLE_NAME, ku.COLUMN_NAME
            FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
            JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE ku
                ON tc.CONSTRAINT_NAME = ku.CONSTRAINT_NAME
                AND tc.TABLE_SCHEMA = ku.TABLE_SCHEMA
                AND tc.TABLE_NAME = ku.TABLE_NAME
            WHERE tc.CONSTRAINT_TYPE = 'PRIMARY KEY'
        ) pk ON c.TABLE_SCHEMA = pk.TABLE_SCHEMA
            AND c.TABLE_NAME = pk.TABLE_NAME
            AND c.COLUMN_NAME = pk.COLUMN_NAME
        WHERE c.TABLE_SCHEMA = ? AND c.TABLE_NAME = ?
        ORDER BY c.ORDINAL_POSITION
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _definir_banco(cursor, banco)
        cursor.execute(sql, (schema, nome_tabela))
        resultado = _format_resultado(cursor)
        if resultado == "[]":
            return f"Tabela '{tabela}' nao encontrada."
        return resultado
    except Exception as e:
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()


def listar_indices(tabela: str, banco: str = "") -> str:
    """Lista todos os indices de uma tabela.

    Args:
        tabela: Nome da tabela. Use 'schema.nome' ou apenas 'nome'.
        banco: Nome do banco de dados (opcional).
    """
    schema = "dbo"
    nome_tabela = tabela
    if "." in tabela:
        schema, nome_tabela = tabela.split(".", 1)

    sql = """
        SELECT
            i.name AS NOME_INDICE,
            i.type_desc AS TIPO,
            i.is_unique AS UNICO,
            i.is_primary_key AS PK,
            STRING_AGG(c.name, ', ') WITHIN GROUP (ORDER BY ic.key_ordinal) AS COLUNAS,
            i.filter_definition AS FILTRO
        FROM sys.indexes i
        JOIN sys.index_columns ic ON i.object_id = ic.object_id AND i.index_id = ic.index_id
        JOIN sys.columns c ON ic.object_id = c.object_id AND ic.column_id = c.column_id
        JOIN sys.tables t ON i.object_id = t.object_id
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE s.name = ? AND t.name = ?
        GROUP BY i.name, i.type_desc, i.is_unique, i.is_primary_key, i.filter_definition
        ORDER BY i.is_primary_key DESC, i.name
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _definir_banco(cursor, banco)
        cursor.execute(sql, (schema, nome_tabela))
        return _format_resultado(cursor)
    except Exception as e:
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()


def listar_procedures(banco: str = "") -> str:
    """Lista todas as stored procedures do banco.

    Args:
        banco: Nome do banco de dados (opcional).
    """
    sql = """
        SELECT
            s.name AS SCHEMA_NAME,
            p.name AS PROCEDURE_NAME,
            p.create_date AS CRIADA_EM,
            p.modify_date AS MODIFICADA_EM
        FROM sys.procedures p
        JOIN sys.schemas s ON p.schema_id = s.schema_id
        ORDER BY s.name, p.name
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _definir_banco(cursor, banco)
        cursor.execute(sql)
        return _format_resultado(cursor)
    except Exception as e:
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()


def ler_procedure(nome: str, banco: str = "") -> str:
    """Retorna o codigo-fonte de uma stored procedure.

    Args:
        nome: Nome da procedure. Use 'schema.nome' ou apenas 'nome'.
        banco: Nome do banco de dados (opcional).
    """
    schema = "dbo"
    nome_proc = nome
    if "." in nome:
        schema, nome_proc = nome.split(".", 1)

    sql = """
        SELECT OBJECT_DEFINITION(OBJECT_ID(? + '.' + ?)) AS CODIGO_FONTE
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _definir_banco(cursor, banco)
        cursor.execute(sql, (schema, nome_proc))
        row = cursor.fetchone()
        if row is None or row[0] is None:
            return f"Procedure '{nome}' nao encontrada."
        return row[0]
    except Exception as e:
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()


def executar_procedure(nome: str, banco: str = "", parametros: str = "") -> str:
    """Executa uma stored procedure. Requer confirmacao explicita do usuario.

    IMPORTANTE: O usuario deve ser questionado antes de executar qualquer procedure.
    Apenas procedures de leitura (que nao modificam dados) devem ser executadas
    sem alerta adicional.

    Args:
        nome: Nome da procedure. Use 'schema.nome' ou apenas 'nome'.
        banco: Nome do banco de dados (opcional).
        parametros: Parametros no formato SQL: 'valor1, valor2, @param=valor'.
    """
    if parametros:
        sql = f"EXEC {nome} {parametros}"
    else:
        sql = f"EXEC {nome}"

    conn = get_connection()
    cursor = conn.cursor()
    try:
        if banco:
            _definir_banco(cursor, banco)
        cursor.execute(sql)
        if cursor.description:
            return "RESULTADO:\n" + _format_resultado(cursor)
        else:
            conn.commit()
            return f"Procedure '{nome}' executada com sucesso (sem resultados)."
    except Exception as e:
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()


def plano_execucao(sql: str) -> str:
    """Exibe o plano de execucao estimado para uma query, sem executa-la.

    Args:
        sql: Query SQL para analisar o plano de execucao.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute("SET SHOWPLAN_XML ON")
        cursor.execute(sql)
        row = cursor.fetchone()
        cursor.execute("SET SHOWPLAN_XML OFF")
        if row:
            return row[0]
        return "Nenhum plano de execucao retornado."
    except Exception as e:
        try:
            cursor.execute("SET SHOWPLAN_XML OFF")
        except Exception:
            pass
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()


def listar_constraints(tabela: str, banco: str = "") -> str:
    """Lista todas as constraints de uma tabela (PK, FK, UNIQUE, CHECK, DEFAULT).

    Args:
        tabela: Nome da tabela. Use 'schema.nome' ou apenas 'nome'.
        banco: Nome do banco de dados (opcional).
    """
    schema = "dbo"
    nome_tabela = tabela
    if "." in tabela:
        schema, nome_tabela = tabela.split(".", 1)

    sql = """
        SELECT
            tc.CONSTRAINT_NAME,
            tc.CONSTRAINT_TYPE,
            STRING_AGG(kcu.COLUMN_NAME, ', ') AS COLUNAS,
            rc.UNIQUE_CONSTRAINT_NAME AS REFERENCIA_FK,
            cc.CHECK_CLAUSE AS EXPRESSAO_CHECK
        FROM INFORMATION_SCHEMA.TABLE_CONSTRAINTS tc
        LEFT JOIN INFORMATION_SCHEMA.KEY_COLUMN_USAGE kcu
            ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME
            AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
            AND tc.TABLE_NAME = kcu.TABLE_NAME
        LEFT JOIN INFORMATION_SCHEMA.REFERENTIAL_CONSTRAINTS rc
            ON tc.CONSTRAINT_NAME = rc.CONSTRAINT_NAME
        LEFT JOIN INFORMATION_SCHEMA.CHECK_CONSTRAINTS cc
            ON tc.CONSTRAINT_NAME = cc.CONSTRAINT_NAME
        WHERE tc.TABLE_SCHEMA = ? AND tc.TABLE_NAME = ?
        GROUP BY tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE,
                 rc.UNIQUE_CONSTRAINT_NAME, cc.CHECK_CLAUSE
        ORDER BY tc.CONSTRAINT_TYPE, tc.CONSTRAINT_NAME
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _definir_banco(cursor, banco)
        cursor.execute(sql, (schema, nome_tabela))
        return _format_resultado(cursor)
    except Exception as e:
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()


def estatisticas_tabela(tabela: str, banco: str = "") -> str:
    """Exibe estatisticas de uma tabela: numero estimado de linhas,
    tamanho em disco e uso de dados.

    Args:
        tabela: Nome da tabela. Use 'schema.nome' ou apenas 'nome'.
        banco: Nome do banco de dados (opcional).
    """
    schema = "dbo"
    nome_tabela = tabela
    if "." in tabela:
        schema, nome_tabela = tabela.split(".", 1)

    sql = """
        SELECT
            t.name AS TABELA,
            p.rows AS LINHAS_ESTIMADAS,
            SUM(a.total_pages) * 8 AS TAMANHO_KB,
            SUM(a.used_pages) * 8 AS USADO_KB,
            SUM(a.data_pages) * 8 AS DADOS_KB
        FROM sys.tables t
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        JOIN sys.indexes i ON t.object_id = i.object_id
        JOIN sys.partitions p ON i.object_id = p.object_id AND i.index_id = p.index_id
        JOIN sys.allocation_units a ON p.partition_id = a.container_id
        WHERE s.name = ? AND t.name = ?
        GROUP BY t.name, p.rows
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _definir_banco(cursor, banco)
        cursor.execute(sql, (schema, nome_tabela))
        return _format_resultado(cursor)
    except Exception as e:
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()


def listar_funcoes(banco: str = "") -> str:
    """Lista todas as funcoes (scalar e table-valued) do banco.

    Args:
        banco: Nome do banco de dados (opcional).
    """
    sql = """
        SELECT
            s.name AS SCHEMA_NAME,
            o.name AS FUNCTION_NAME,
            o.type_desc AS TIPO,
            o.create_date AS CRIADA_EM,
            o.modify_date AS MODIFICADA_EM
        FROM sys.objects o
        JOIN sys.schemas s ON o.schema_id = s.schema_id
        WHERE o.type IN ('FN', 'IF', 'TF', 'FS', 'FT')
        ORDER BY s.name, o.name
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _definir_banco(cursor, banco)
        cursor.execute(sql)
        return _format_resultado(cursor)
    except Exception as e:
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()


def ler_funcao(nome: str, banco: str = "") -> str:
    """Retorna o codigo-fonte de uma funcao.

    Args:
        nome: Nome da funcao. Use 'schema.nome' ou apenas 'nome'.
        banco: Nome do banco de dados (opcional).
    """
    schema = "dbo"
    nome_func = nome
    if "." in nome:
        schema, nome_func = nome.split(".", 1)

    sql = """
        SELECT OBJECT_DEFINITION(OBJECT_ID(? + '.' + ?)) AS CODIGO_FONTE
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _definir_banco(cursor, banco)
        cursor.execute(sql, (schema, nome_func))
        row = cursor.fetchone()
        if row is None or row[0] is None:
            return f"Funcao '{nome}' nao encontrada."
        return row[0]
    except Exception as e:
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()
