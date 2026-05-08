import sys
import logging
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool

from . import tools
from .connection import close_connection

logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("mcp-sqlserver")

servidor = Server("mcp-sqlserver")


@servidor.list_tools()
async def listar_ferramentas():
    return [
        Tool(
            name="consulta",
            description="Executa uma consulta SELECT (somente leitura) no SQL Server. "
                        "Use notacao de tres niveis para acessar outros bancos: "
                        "banco.esquema.tabela. "
                        "Operacoes DDL/DML (INSERT, UPDATE, DELETE, DROP, etc.) sao bloqueadas.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Query SQL do tipo SELECT.",
                    },
                },
                "required": ["sql"],
            },
        ),
        Tool(
            name="listar_bancos",
            description="Lista todos os bancos de dados acessiveis no servidor.",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="listar_tabelas",
            description="Lista todas as tabelas e views de um banco de dados.",
            inputSchema={
                "type": "object",
                "properties": {
                    "banco": {
                        "type": "string",
                        "description": "Nome do banco de dados (opcional). "
                                       "Se nao informado, usa o banco padrao da conexao.",
                        "default": "",
                    },
                },
            },
        ),
        Tool(
            name="descrever_tabela",
            description="Descreve a estrutura de uma tabela: colunas, tipos, "
                        "nulabilidade e chave primaria.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tabela": {
                        "type": "string",
                        "description": "Nome da tabela. Use 'schema.nome' ou apenas 'nome' (default: dbo).",
                    },
                    "banco": {
                        "type": "string",
                        "description": "Nome do banco de dados (opcional).",
                        "default": "",
                    },
                },
                "required": ["tabela"],
            },
        ),
        Tool(
            name="listar_indices",
            description="Lista todos os indices de uma tabela especifica.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tabela": {
                        "type": "string",
                        "description": "Nome da tabela. Use 'schema.nome' ou apenas 'nome'.",
                    },
                    "banco": {
                        "type": "string",
                        "description": "Nome do banco de dados (opcional).",
                        "default": "",
                    },
                },
                "required": ["tabela"],
            },
        ),
        Tool(
            name="listar_procedures",
            description="Lista todas as stored procedures de um banco de dados.",
            inputSchema={
                "type": "object",
                "properties": {
                    "banco": {
                        "type": "string",
                        "description": "Nome do banco de dados (opcional).",
                        "default": "",
                    },
                },
            },
        ),
        Tool(
            name="ler_procedure",
            description="Retorna o codigo-fonte completo de uma stored procedure.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nome": {
                        "type": "string",
                        "description": "Nome da procedure. Use 'schema.nome' ou apenas 'nome'.",
                    },
                    "banco": {
                        "type": "string",
                        "description": "Nome do banco de dados (opcional).",
                        "default": "",
                    },
                },
                "required": ["nome"],
            },
        ),
        Tool(
            name="executar_procedure",
            description="Executa uma stored procedure. "
                        "ATENCAO: o usuario DEVE ser questionado e confirmar antes de cada execucao. "
                        "Nunca execute procedures sem permissao explicita.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nome": {
                        "type": "string",
                        "description": "Nome da procedure. Use 'schema.nome' ou apenas 'nome'.",
                    },
                    "banco": {
                        "type": "string",
                        "description": "Nome do banco de dados (opcional).",
                        "default": "",
                    },
                    "parametros": {
                        "type": "string",
                        "description": "Parametros no formato SQL: 'valor1, valor2, @param=valor'.",
                        "default": "",
                    },
                },
                "required": ["nome"],
            },
        ),
        Tool(
            name="plano_execucao",
            description="Exibe o plano de execucao estimado para uma query, sem executa-la. "
                        "Util para analisar performance.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Query SQL para analisar o plano de execucao.",
                    },
                },
                "required": ["sql"],
            },
        ),
        Tool(
            name="listar_constraints",
            description="Lista todas as constraints de uma tabela (PK, FK, UNIQUE, CHECK, DEFAULT).",
            inputSchema={
                "type": "object",
                "properties": {
                    "tabela": {
                        "type": "string",
                        "description": "Nome da tabela. Use 'schema.nome' ou apenas 'nome'.",
                    },
                    "banco": {
                        "type": "string",
                        "description": "Nome do banco de dados (opcional).",
                        "default": "",
                    },
                },
                "required": ["tabela"],
            },
        ),
        Tool(
            name="estatisticas_tabela",
            description="Exibe estatisticas de uma tabela: numero estimado de linhas, "
                        "tamanho em disco e uso de dados.",
            inputSchema={
                "type": "object",
                "properties": {
                    "tabela": {
                        "type": "string",
                        "description": "Nome da tabela. Use 'schema.nome' ou apenas 'nome'.",
                    },
                    "banco": {
                        "type": "string",
                        "description": "Nome do banco de dados (opcional).",
                        "default": "",
                    },
                },
                "required": ["tabela"],
            },
        ),
        Tool(
            name="listar_funcoes",
            description="Lista todas as funcoes (scalar e table-valued) de um banco de dados.",
            inputSchema={
                "type": "object",
                "properties": {
                    "banco": {
                        "type": "string",
                        "description": "Nome do banco de dados (opcional).",
                        "default": "",
                    },
                },
            },
        ),
        Tool(
            name="ler_funcao",
            description="Retorna o codigo-fonte completo de uma funcao.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nome": {
                        "type": "string",
                        "description": "Nome da funcao. Use 'schema.nome' ou apenas 'nome'.",
                    },
                    "banco": {
                        "type": "string",
                        "description": "Nome do banco de dados (opcional).",
                        "default": "",
                    },
                },
                "required": ["nome"],
            },
        ),
        Tool(
            name="status_jobs",
            description="Retorna o status da ultima execucao de jobs do SQL Server Agent. "
                        "Recebe uma lista de nomes de jobs separados por virgula e retorna "
                        "inicio, fim, duracao, resultado e mensagem de cada job.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nomes": {
                        "type": "string",
                        "description": "Nomes dos jobs separados por virgula. "
                                       "Exemplo: 'Job A, Job B, Job C'",
                    },
                },
                "required": ["nomes"],
            },
        ),
        Tool(
            name="executar_update",
            description="Executa um comando UPDATE no SQL Server. "
                        "ATENCAO: o usuario DEVE ser questionado e confirmar antes de cada execucao. "
                        "Nunca execute updates sem permissao explicita. "
                        "A clausula WHERE e obrigatoria para evitar alteracoes em massa.",
            inputSchema={
                "type": "object",
                "properties": {
                    "sql": {
                        "type": "string",
                        "description": "Comando SQL UPDATE completo. Deve incluir clausula WHERE.",
                    },
                },
                "required": ["sql"],
            },
        ),
        Tool(
            name="alterar_procedure",
            description="Altera uma stored procedure com backup previo do codigo original. "
                        "ATENCAO: o usuario DEVE ser questionado e confirmar antes de cada execucao. "
                        "Nunca altere procedures sem permissao explicita. "
                        "Fluxo: 1) le o codigo atual, 2) salva backup no arquivo indicado, "
                        "3) verifica o backup, 4) executa o ALTER PROCEDURE.",
            inputSchema={
                "type": "object",
                "properties": {
                    "nome": {
                        "type": "string",
                        "description": "Nome da procedure. Use 'schema.nome' ou apenas 'nome'.",
                    },
                    "script": {
                        "type": "string",
                        "description": "Script ALTER PROCEDURE completo.",
                    },
                    "backup_arquivo": {
                        "type": "string",
                        "description": "Caminho absoluto do arquivo onde sera salvo o backup do codigo original.",
                    },
                    "banco": {
                        "type": "string",
                        "description": "Nome do banco de dados (opcional).",
                        "default": "",
                    },
                },
                "required": ["nome", "script", "backup_arquivo"],
            },
        ),
    ]


@servidor.call_tool()
async def chamar_ferramenta(name: str, arguments: dict):
    logger.info(f"Ferramenta chamada: {name} com argumentos: {arguments}")

    mapeamento = {
        "consulta": tools.consulta,
        "listar_bancos": tools.listar_bancos,
        "listar_tabelas": tools.listar_tabelas,
        "descrever_tabela": tools.descrever_tabela,
        "listar_indices": tools.listar_indices,
        "listar_procedures": tools.listar_procedures,
        "ler_procedure": tools.ler_procedure,
        "executar_procedure": tools.executar_procedure,
        "plano_execucao": tools.plano_execucao,
        "listar_constraints": tools.listar_constraints,
        "estatisticas_tabela": tools.estatisticas_tabela,
        "listar_funcoes": tools.listar_funcoes,
        "ler_funcao": tools.ler_funcao,
        "status_jobs": tools.status_jobs,
        "executar_update": tools.executar_update,
        "alterar_procedure": tools.alterar_procedure,
    }

    func = mapeamento.get(name)
    if func is None:
        return [{"type": "text", "text": f"Ferramenta desconhecida: {name}"}]

    resultado = func(**arguments)
    return [{"type": "text", "text": resultado}]


async def executar():
    async with stdio_server() as (read_stream, write_stream):
        await servidor.run(read_stream, write_stream, servidor.create_initialization_options())


def main():
    import asyncio
    try:
        asyncio.run(executar())
    except KeyboardInterrupt:
        pass
    finally:
        close_connection()


if __name__ == "__main__":
    main()
