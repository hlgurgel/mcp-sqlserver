# mcp-sqlserver

[![PyPI version](https://img.shields.io/pypi/v/sqlserver-mcp-tools.svg)](https://pypi.org/project/sqlserver-mcp-tools/)
[![License: MIT](https://img.shields.io/github/license/hlgurgel/mcp-sqlserver.svg)](https://github.com/hlgurgel/mcp-sqlserver/blob/main/LICENSE)
[![Python versions](https://img.shields.io/pypi/pyversions/sqlserver-mcp-tools.svg)](https://pypi.org/project/sqlserver-mcp-tools/)

Servidor MCP (Model Context Protocol) para SQL Server, com controle de permissões
e modo somente-leitura por padrão. Permite que agentes de IA (Claude, opencode e
outros clientes MCP) consultem e administrem bancos SQL Server de forma segura.

## Segurança

- **Credenciais nunca expostas ao LLM** — a string de conexão é lida do ambiente
  e nunca aparece nas respostas nem nos logs.
- **Somente leitura por padrão** — a ferramenta `consulta` bloqueia DDL/DML
  (INSERT, UPDATE, DELETE, DROP, etc.).
- **Escrita sob demanda** — ferramentas de escrita (`executar_update`, `executar_ddl`,
  etc.) só são expostas quando o usuário da conexão possui permissão de escrita
  (roles `sysadmin`, `db_owner`, `db_datawriter` ou `db_ddladmin`), e exigem
  confirmação explícita antes de cada execução.

## Pré-requisitos

- Python 3.10+
- Driver **ODBC Driver 18 for SQL Server**:
  - macOS: `brew install msodbcsql18`
  - Windows/Linux: instale o driver correspondente da Microsoft

## Instalação

Via PyPI:

```bash
pip install sqlserver-mcp-tools
```

Ou, sem instalar nada (executa direto do PyPI com cache):

```bash
uvx --from sqlserver-mcp-tools mcp-sqlserver
```

## Configuração

O servidor lê a string de conexão das seguintes fontes, em ordem de prioridade:

1. Variável de ambiente `MSSQL_CONNECTION_STRING`
2. Variável de ambiente `MSSQL_ENV_FILE` apontando para um arquivo `.env`
3. Arquivo `.env` no diretório de trabalho (ou na raiz do projeto)

Exemplo de string de conexão:

```
DRIVER={ODBC Driver 18 for SQL Server};SERVER=localhost,1433;DATABASE=seu_banco;UID=seu_usuario;PWD=sua_senha;TrustServerCertificate=yes
```

## Uso com clientes MCP

### Claude Desktop

Adicione ao `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "mcp-sqlserver": {
      "command": "uvx",
      "args": ["--from", "sqlserver-mcp-tools", "mcp-sqlserver"],
      "env": {
        "MSSQL_CONNECTION_STRING": "DRIVER={ODBC Driver 18 for SQL Server};SERVER=...;DATABASE=...;UID=...;PWD=...;TrustServerCertificate=yes"
      }
    }
  }
}
```

Se instalou via `pip install`, pode usar o entry point diretamente:

```json
{
  "mcpServers": {
    "mcp-sqlserver": {
      "command": "mcp-sqlserver",
      "env": {
        "MSSQL_CONNECTION_STRING": "DRIVER={ODBC Driver 18 for SQL Server};SERVER=...;DATABASE=...;UID=...;PWD=...;TrustServerCertificate=yes"
      }
    }
  }
}
```

### OpenCode

No `opencode.json` do projeto:

```json
{
  "mcp": {
    "sqlserver": {
      "type": "local",
      "command": ["mcp-sqlserver"],
      "environment": {
        "MSSQL_CONNECTION_STRING": "DRIVER={ODBC Driver 18 for SQL Server};SERVER=...;DATABASE=...;UID=...;PWD=...;TrustServerCertificate=yes"
      }
    }
  }
}
```

Alternativa: apontar para um arquivo `.env` local, mantendo a senha fora do JSON:

```json
{
  "mcp": {
    "sqlserver": {
      "type": "local",
      "command": ["mcp-sqlserver"],
      "environment": {
        "MSSQL_ENV_FILE": "/caminho/para/seu/.env"
      }
    }
  }
}
```

## Ferramentas disponíveis

Somente leitura (sempre disponíveis):

| Ferramenta | Descrição |
|---|---|
| `consulta` | Executa SELECT (somente leitura, bloqueia DDL/DML) |
| `listar_bancos` | Lista os bancos de dados acessíveis |
| `listar_tabelas` | Lista tabelas e views de um banco |
| `descrever_tabela` | Estrutura de uma tabela (colunas, tipos, PK) |
| `listar_indices` | Índices de uma tabela |
| `listar_procedures` | Lista stored procedures |
| `ler_procedure` | Código-fonte de uma procedure |
| `listar_funcoes` | Lista funções (scalar e table-valued) |
| `ler_funcao` | Código-fonte de uma função |
| `listar_constraints` | Constraints de uma tabela (PK, FK, UNIQUE, CHECK, DEFAULT) |
| `estatisticas_tabela` | Estatísticas (linhas, tamanho, uso de dados) |
| `plano_execucao` | Plano de execução estimado (sem executar) |
| `status_jobs` | Status da última execução de jobs do SQL Agent |

Escrita (só com permissão de escrita na conexão):

| Ferramenta | Descrição |
|---|---|
| `executar_procedure` | Executa uma stored procedure |
| `executar_update` | Executa UPDATE (exige WHERE) |
| `criar_indice` | Cria índice |
| `alterar_procedure` | Altera procedure com backup automático |
| `executar_ddl` | Executa DDL com backup do script de reversão |

## Licença

MIT
