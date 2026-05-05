# mcp-sqlserver

Servidor MCP (Model Context Protocol) para SQL Server com controle de permissões.

## Segurança

- **Credenciais nunca expostas ao LLM** — o servidor lê a string de conexão do ambiente e nunca a expõe nas respostas
- **Somente leitura por padrão** — ferramenta `consulta` bloqueia DDL/DML (INSERT, UPDATE, DELETE, DROP, etc.)
- **Permissionamento interativo** — `executar_procedure` exige confirmação explícita do usuário

## Pré-requisitos

- Python 3.10+
- Driver ODBC 18 for SQL Server (`brew install msodbcsql18`)

## Instalação

```bash
pip install -e .
```

## Configuração

Copie `.env.example` para `.env` e preencha a string de conexão:

```bash
cp .env.example .env
```

## Uso com OpenCode

No `opencode.json` do projeto:

```json
{
  "mcp": {
    "sqlserver": {
      "type": "local",
      "command": "python3",
      "args": ["-m", "mcp_sqlserver.server"],
      "cwd": "caminho/para/mcp-sqlserver/src",
      "env": {
        "MSSQL_CONNECTION_STRING": "{env:MSSQL_CONNECTION_STRING}"
      }
    }
  }
}
```

## Ferramentas Disponíveis

| Ferramenta | Descrição |
|---|---|
| `consulta` | Executa SELECT (somente leitura) |
| `listar_tabelas` | Lista todas as tabelas |
| `descrever_tabela` | Estrutura de uma tabela |
| `listar_indices` | Índices de uma tabela |
| `listar_procedures` | Lista todas as procedures |
| `ler_procedure` | Código-fonte de uma procedure |
| `executar_procedure` | Executa uma procedure (exige confirmação) |
| `plano_execucao` | Plano de execução estimado |
| `listar_constraints` | Constraints de uma tabela |
| `estatisticas_tabela` | Estatísticas (linhas, tamanho) |
| `listar_funcoes` | Lista funções |
| `ler_funcao` | Código-fonte de uma função |
