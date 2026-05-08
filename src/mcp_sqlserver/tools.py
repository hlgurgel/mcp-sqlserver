import json
import re
from .connection import get_connection, get_connection_string

MAX_ROWS = 2000

_BANCO_PADRAO = "master"
_conn_str = get_connection_string()
for _parte in _conn_str.split(";"):
    if _parte.strip().upper().startswith("DATABASE="):
        _BANCO_PADRAO = _parte.split("=", 1)[1].strip()
        break


def _validar_identificador_sql(nome: str) -> bool:
    return bool(re.match(
        r'^\[?[a-zA-Z_][a-zA-Z0-9_$\s]*\]?'
        r'(\.[a-zA-Z_][a-zA-Z0-9_$\s]*\]?)*$',
        nome
    ))


_PALAVRAS_PROIBIDAS = [
    "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE", "ALTER",
    "CREATE", "EXEC", "EXECUTE", "MERGE", "GRANT", "REVOKE",
    "BACKUP", "RESTORE", "DBCC",
]


def _validar_sem_injecao(texto: str) -> bool:
    if not texto:
        return True
    for char in [";", "--", "/*", "*/"]:
        if char in texto:
            return False
    texto_upper = texto.upper()
    for palavra in _PALAVRAS_PROIBIDAS:
        if re.search(r'\b' + palavra + r'\b', texto_upper):
            return False
    return True


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
    for palavra in _PALAVRAS_PROIBIDAS:
        if sql_upper.startswith(palavra) or f"\n{palavra}" in sql_upper:
            return f"OPERACAO BLOQUEADA: '{palavra}' nao permitido. Apenas SELECT."

    if ";" in sql:
        return "OPERACAO BLOQUEADA: Comandos encadeados (;) nao sao permitidos."

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
            STUFF((
                SELECT ', ' + c2.name
                FROM sys.index_columns ic2
                JOIN sys.columns c2
                    ON ic2.object_id = c2.object_id
                    AND ic2.column_id = c2.column_id
                WHERE ic2.object_id = i.object_id
                  AND ic2.index_id = i.index_id
                ORDER BY ic2.key_ordinal
                FOR XML PATH('')
            ), 1, 2, '') AS COLUNAS,
            i.filter_definition AS FILTRO
        FROM sys.indexes i
        JOIN sys.tables t ON i.object_id = t.object_id
        JOIN sys.schemas s ON t.schema_id = s.schema_id
        WHERE s.name = ? AND t.name = ?
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
    if not _validar_identificador_sql(nome):
        return "OPERACAO BLOQUEADA: Nome de procedure invalido. Use apenas identificadores SQL validos (schema.procedure)."

    if not _validar_sem_injecao(parametros):
        return "OPERACAO BLOQUEADA: Parametros contem comandos SQL nao permitidos."

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


def status_jobs(nomes: str) -> str:
    """Retorna o status da ultima execucao de jobs do SQL Server Agent.

    Args:
        nomes: Lista de nomes de jobs separados por virgula.
               Exemplo: 'Job A, Job B, Job C'
    """
    import json as _json

    lista_nomes = [n.strip() for n in nomes.split(",") if n.strip()]
    if not lista_nomes:
        return "[]"

    placeholders = ", ".join(["?" for _ in lista_nomes])

    sql = f"""
    WITH ultima_atividade AS (
        SELECT
            job_id,
            start_execution_date,
            stop_execution_date,
            ROW_NUMBER() OVER (
                PARTITION BY job_id
                ORDER BY
                    start_execution_date DESC,
                    CASE WHEN stop_execution_date IS NOT NULL THEN 0 ELSE 1 END
            ) AS rn
        FROM msdb.dbo.sysjobactivity
        WHERE start_execution_date IS NOT NULL
    ),
    ultimo_historico AS (
        SELECT
            job_id,
            instance_id,
            run_status,
            message,
            ROW_NUMBER() OVER (
                PARTITION BY job_id
                ORDER BY instance_id DESC
            ) AS rn
        FROM msdb.dbo.sysjobhistory
        WHERE step_id = 0
    )
    SELECT
        j.name AS nome,
        FORMAT(ja.start_execution_date, 'yyyy-MM-ddTHH:mm:ss') AS inicio,
        FORMAT(ja.stop_execution_date, 'yyyy-MM-ddTHH:mm:ss') AS fim,
        DATEDIFF(MINUTE, ja.start_execution_date, ja.stop_execution_date) AS duracao_minutos,
        CASE jh.run_status
            WHEN 0 THEN 'FALHA'
            WHEN 1 THEN 'SUCESSO'
            WHEN 2 THEN 'TENTATIVA'
            WHEN 3 THEN 'CANCELADO'
            WHEN 4 THEN 'EM EXECUCAO'
            ELSE 'DESCONHECIDO'
        END AS resultado,
        CASE
            WHEN ja.stop_execution_date IS NULL AND ja.start_execution_date IS NOT NULL THEN 1
            ELSE 0
        END AS em_execucao,
        COALESCE(jh.message, 'Sem historico recente') AS mensagem
    FROM msdb.dbo.sysjobs j
    LEFT JOIN ultima_atividade ja
        ON j.job_id = ja.job_id
        AND ja.rn = 1
    LEFT JOIN ultimo_historico jh
        ON j.job_id = jh.job_id
        AND jh.rn = 1
    WHERE j.name IN ({placeholders})
    ORDER BY ja.start_execution_date
    """

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql, lista_nomes)
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


def alterar_procedure(nome: str, script: str, backup_arquivo: str, banco: str = "") -> str:
    """Altera uma stored procedure com backup previo do codigo original.

    ATENCAO: O usuario DEVE ser questionado e confirmar antes de cada execucao.
    Nunca execute ALTER PROCEDURE sem permissao explicita.

    Fluxo:
    1. Le o codigo-fonte atual da procedure
    2. Salva o backup em 'backup_arquivo'
    3. Verifica se o backup foi salvo corretamente
    4. Executa o ALTER PROCEDURE
    5. Retorna status da operacao

    Args:
        nome: Nome da procedure. Use 'schema.nome' ou apenas 'nome'.
        script: Script ALTER PROCEDURE completo.
        backup_arquivo: Caminho absoluto do arquivo onde sera salvo o backup.
        banco: Nome do banco de dados (opcional).
    """
    import os as _os
    from datetime import datetime as _dt

    schema = "dbo"
    nome_proc = nome
    if "." in nome:
        schema, nome_proc = nome.split(".", 1)

    # 1. Valida identificador
    if not _validar_identificador_sql(nome):
        return "OPERACAO BLOQUEADA: Nome de procedure invalido."

    # 2. Le codigo atual
    sql_ler = """
        SELECT OBJECT_DEFINITION(OBJECT_ID(? + '.' + ?)) AS CODIGO_FONTE
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        _definir_banco(cursor, banco)
        cursor.execute(sql_ler, (schema, nome_proc))
        row = cursor.fetchone()
        if row is None or row[0] is None:
            return f"ERRO: Procedure '{nome}' nao encontrada. Backup abortado."
        codigo_original = row[0]
    except Exception as e:
        return f"ERRO ao ler procedure para backup: {str(e)}"
    finally:
        cursor.close()

    # 3. Salva backup
    try:
        _os.makedirs(_os.path.dirname(backup_arquivo), exist_ok=True)
        with open(backup_arquivo, "w", encoding="utf-8") as f:
            f.write(f"-- Backup automatico de {schema}.{nome_proc}\n")
            f.write(f"-- Data: {_dt.now().isoformat()}\n")
            f.write(f"-- Banco: {banco or _BANCO_PADRAO}\n")
            f.write("-- ============================================================\n\n")
            f.write(codigo_original)
    except Exception as e:
        return f"ERRO ao salvar backup em '{backup_arquivo}': {str(e)}"

    # 4. Verifica backup (existe e tem tamanho minimo)
    try:
        tamanho_backup = _os.path.getsize(backup_arquivo)
        if tamanho_backup < 50:
            return f"ERRO: Verificacao de backup falhou. O arquivo '{backup_arquivo}' tem apenas {tamanho_backup} bytes."
    except Exception as e:
        return f"ERRO ao verificar backup: {str(e)}"

    # 5. Valida script ALTER (apenas verifica se comeca com ALTER PROCEDURE)
    script_upper = script.strip().upper()
    if not script_upper.startswith("ALTER PROCEDURE") and not script_upper.startswith("ALTER PROC"):
        return "OPERACAO BLOQUEADA: O script deve comecar com ALTER PROCEDURE."

    # 6. Executa ALTER
    cursor = conn.cursor()
    try:
        _definir_banco(cursor, banco)
        cursor.execute(script)
        conn.commit()
        return (
            f"SUCESSO: Procedure '{schema}.{nome_proc}' alterada com sucesso.\n"
            f"Backup salvo em: {backup_arquivo} "
            f"({len(codigo_original)} caracteres)"
        )
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return f"ERRO ao executar ALTER: {str(e)}\n\nBackup salvo em: {backup_arquivo} (use para restaurar)"
    finally:
        cursor.close()


def executar_update(sql: str) -> str:
    """Executa um comando UPDATE no SQL Server.

    ATENCAO: O usuario DEVE ser questionado e confirmar antes de cada execucao.
    Nunca execute updates sem permissao explicita.

    Args:
        sql: Comando SQL UPDATE completo. Deve incluir clausula WHERE.
    """
    sql_upper = sql.strip().upper()

    if not sql_upper.startswith("UPDATE"):
        return "OPERACAO BLOQUEADA: Apenas comandos UPDATE sao permitidos."

    for palavra in _PALAVRAS_PROIBIDAS:
        if palavra == "UPDATE":
            continue
        if re.search(r'\b' + palavra + r'\b', sql_upper):
            return f"OPERACAO BLOQUEADA: '{palavra}' nao permitido em comandos UPDATE."

    if ";" in sql:
        return "OPERACAO BLOQUEADA: Comandos encadeados (;) nao sao permitidos."

    if "--" in sql or "/*" in sql:
        return "OPERACAO BLOQUEADA: Comentarios SQL nao sao permitidos em comandos UPDATE."

    if "WHERE" not in sql_upper:
        return "OPERACAO BLOQUEADA: UPDATE sem clausula WHERE. Forneca uma condicao WHERE para evitar alteracoes em massa."

    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(sql)
        conn.commit()
        linhas_afetadas = cursor.rowcount
        return f"UPDATE executado com sucesso. Linhas afetadas: {linhas_afetadas}"
    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        return f"ERRO: {str(e)}"
    finally:
        cursor.close()
