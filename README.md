# Pipeline de Dados Meta Graph API

[![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-2.7.3-017CEE?style=flat&logo=Apache%20Airflow&logoColor=white)](https://airflow.apache.org/)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQL Server](https://img.shields.io/badge/SQL%20Server-CC2927?style=flat&logo=microsoft-sql-server&logoColor=white)](https://www.microsoft.com/sql-server)

Pipeline de dados escalável e pronto para produção usando Apache Airflow para extrair, transformar e carregar dados de publicidade da Meta Graph API (Facebook & Instagram) através de múltiplas contas do Business Manager.

## 🎯 Visão Geral

Este projeto demonstra uma solução robusta de engenharia de dados para gerenciar dados de publicidade de múltiplas contas do Meta Business Manager. Apresenta:

- **Orquestração multi-conta** - Gerencia 10+ contas publicitárias com rotação inteligente de tokens
- **Processamento paralelo** - Task groups para performance otimizada de extração
- **Arquitetura enterprise** - Separação de responsabilidades, gerenciamento de configuração e tratamento de erros
- **Sincronização de banco de dados** - Estratégia dual-database (PostgreSQL para data lake, SQL Server para analytics)
- **Boas práticas de produção** - Configuração baseada em variáveis de ambiente, logging completo, mecanismos de retry

## 🏗️ Arquitetura

```
┌─────────────────────────────────────────────────────────────────┐
│                      Apache Airflow DAG                         │
│                                                                 │
│  ┌──────────────┐      ┌──────────────┐                        │
│  │ Task Group 1 │      │ Task Group 2 │                        │
│  │ Contas 1-5   │  →   │ Contas 6-10  │   →   ┌─────────────┐ │
│  │  (Paralelo)  │      │  (Paralelo)  │       │ Sync SQL    │ │
│  └──────────────┘      └──────────────┘       └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                ↓                                        ↓
      ┌──────────────────┐                    ┌──────────────────┐
      │   PostgreSQL     │                    │   SQL Server     │
      │   (Data Lake)    │    ═══════>        │   (Analytics)    │
      │                  │    Sync Views      │                  │
      │ • Dados brutos   │                    │ • Dados agregados│
      │ • Dados actions  │                    │ • Views negócio  │
      │ • Multi-contas   │                    │ • Relatórios     │
      └──────────────────┘                    └──────────────────┘
```

### Componentes Principais

1. **Orquestrador DAG** ([meta_graph_api_pipeline.py](dags/meta_graph_api_pipeline.py))
   - Agenda e coordena todas as tarefas
   - Gerencia execução paralela com task groups
   - Lida com retries e cenários de falha

2. **Cliente Graph API** ([utils/graph_api.py](utils/graph_api.py))
   - Abstrai interações com Meta Graph API
   - Implementa paginação e rate limiting
   - Processa e transforma respostas da API

3. **Gerenciador de Banco de Dados** ([utils/database.py](utils/database.py))
   - Gerencia todas as operações de banco de dados
   - Implementa padrão upsert para consistência de dados
   - Gerencia sincronização cross-database

4. **Camada de Configuração** ([config/accounts_config.py](config/accounts_config.py))
   - Configuração baseada em variáveis de ambiente
   - Gerenciamento multi-conta com rotação de tokens
   - Validação e verificação de erros

## 🚀 Funcionalidades

### Gerenciamento Multi-Conta
- **Configuração dinâmica de contas** via variáveis de ambiente
- **Rotação inteligente de tokens** para distribuir limites de rate da API
- **Processamento paralelo** com task groups configuráveis
- **Tabelas por conta** para isolamento e escalabilidade de dados

### Pipeline de Dados Robusto
- **Cargas incrementais** com período de retenção configurável (padrão: 15 dias)
- **Operações upsert** para prevenir duplicatas
- **Tratamento de erros abrangente** com retries automáticos
- **Gerenciamento de rate limit** com backoff exponencial

### Recursos Enterprise
- **Configuração baseada em ambiente** - Sem credenciais hardcoded
- **Arquitetura modular** - Separação clara de responsabilidades
- **Logging abrangente** - Visibilidade completa da execução do pipeline
- **Sincronização de banco de dados** - Propagação automática de dados
- **Design escalável** - Fácil adicionar novas contas ou fontes de dados

## 📋 Pré-requisitos

- Python 3.8+
- Apache Airflow 2.7.3+
- PostgreSQL 12+
- SQL Server 2019+ (ou Azure SQL Database)
- Conta(s) Meta Business Manager com acesso à API

## 🛠️ Instalação

### 1. Clonar o Repositório

```bash
git clone https://github.com/seu-usuario/meta-ads-data-pipeline.git
cd meta-ads-data-pipeline
```

### 2. Criar Ambiente Virtual

```bash
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac
```

### 3. Instalar Dependências

```bash
pip install -r requirements.txt
```

### 4. Configurar Variáveis de Ambiente

Copie o arquivo de exemplo e configure com suas credenciais:

```bash
cp .env.example .env
```

Edite o `.env` com suas configurações:

```bash
# Configuração PostgreSQL
POSTGRES_HOST=seu-host-postgres
POSTGRES_PORT=5432
POSTGRES_USER=seu-usuario
POSTGRES_PASSWORD=sua-senha
POSTGRES_DATABASE=seu-database
POSTGRES_SCHEMA=seu-schema

# Configuração SQL Server
SQLSERVER_HOST=seu-sqlserver.database.windows.net
SQLSERVER_PORT=1433
SQLSERVER_DATABASE=seu-database
SQLSERVER_USER=seu-usuario
SQLSERVER_PASSWORD=sua-senha
SQLSERVER_SCHEMA=graph

# Configuração Meta Graph API
GRAPH_API_TOKENS=token1,token2,token3
META_ACCOUNTS=id_conta_1:bm_01,id_conta_2:bm_02,id_conta_3:bm_03

# Configuração da API
GRAPH_API_VERSION=v19.0
DATA_RETENTION_DAYS=15
```

### 5. Configurar Banco de Dados

Crie as tabelas necessárias no PostgreSQL:

```sql
-- Criar schema
CREATE SCHEMA IF NOT EXISTS seu_schema;

-- Criar tabela de exemplo para ads
CREATE TABLE seu_schema.bm_01 (
    unique_id VARCHAR(32) PRIMARY KEY,
    account_id VARCHAR(50),
    account_name VARCHAR(255),
    campaign_id VARCHAR(50),
    campaign_name VARCHAR(255),
    campaign_status VARCHAR(50),
    adset_id VARCHAR(50),
    adset_name VARCHAR(255),
    ad_id VARCHAR(50),
    ad_name VARCHAR(255),
    objective VARCHAR(100),
    spend DECIMAL(10, 2),
    clicks INTEGER,
    inline_link_clicks INTEGER,
    impressions INTEGER,
    date DATE
);

-- Criar tabela de actions
CREATE TABLE seu_schema.bm_01_actions (
    account_id VARCHAR(50),
    ad_id VARCHAR(50),
    action_type VARCHAR(100),
    value INTEGER,
    date DATE
);

-- Criar views para consolidação de dados
CREATE VIEW seu_schema.vw_graph_ads AS
SELECT * FROM seu_schema.bm_01
UNION ALL
SELECT * FROM seu_schema.bm_02
-- ... adicione todas as suas tabelas de contas
;
```

### 6. Inicializar Airflow

```bash
# Inicializar banco de dados do Airflow
airflow db init

# Criar usuário admin
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com
```

## 🎮 Uso

### Iniciar Airflow

```bash
# Iniciar web server (porta padrão 8080)
airflow webserver --port 8080

# Em outro terminal, iniciar o scheduler
airflow scheduler
```

### Acessar Interface do Airflow

Navegue para `http://localhost:8080` e faça login com suas credenciais.

### Habilitar a DAG

1. Encontre a DAG chamada `meta_graph_api_pipeline`
2. Alterne para "On"
3. A DAG executará conforme agendamento: **8:00, 14:00, 20:00 (Seg-Sáb)**

### Trigger Manual

Você pode disparar manualmente a DAG pela UI ou CLI:

```bash
airflow dags trigger meta_graph_api_pipeline
```

## 📊 Fluxo de Dados

### Fase de Extração
1. DAG dispara task groups paralelos
2. Cada task busca dados de uma conta via Graph API
3. Dados incluem:
   - Métricas de performance de anúncios (gasto, cliques, impressões)
   - Informações e status de campanhas
   - Ações e eventos de conversão
4. Dados são validados e transformados

### Fase de Carregamento
1. Dados são inseridos no PostgreSQL em tabelas específicas por conta
2. Duplicatas são prevenidas usando hash unique_id
3. Dados históricos mantidos baseado na política de retenção

### Fase de Sincronização
1. Views do PostgreSQL agregam dados de todas as contas
2. Dados são sincronizados para SQL Server para analytics
3. Registros antigos são deletados antes de inserir novos
4. Threads paralelas otimizam transferências de grandes volumes

## 🔧 Configuração

### Adicionar Novas Contas

Simplesmente atualize seu arquivo `.env`:

```bash
META_ACCOUNTS=contas_existentes,nova_conta_id:bm_11
GRAPH_API_TOKENS=tokens_existentes,novo_token
```

O pipeline descobre e processa automaticamente as novas contas.

### Ajustar Agendamento

Modifique o `SCHEDULE_INTERVAL` em [meta_graph_api_pipeline.py](dags/meta_graph_api_pipeline.py):

```python
SCHEDULE_INTERVAL = "0 8,14,20 * * 1-6"  # Formato cron
```

### Customizar Retenção de Dados

Atualize o `.env`:

```bash
DATA_RETENTION_DAYS=30  # Buscar últimos 30 dias ao invés de 15
```

## 🏆 Boas Práticas Demonstradas

### Organização de Código
- ✅ **Design modular** - Módulos separados para API, database e configuração
- ✅ **Princípio DRY** - Funções e classes reutilizáveis
- ✅ **Nomenclatura clara** - Código auto-documentado com nomes descritivos

### Gerenciamento de Configuração
- ✅ **Variáveis de ambiente** - Sem credenciais hardcoded
- ✅ **`.env.example`** - Template para fácil configuração
- ✅ **Validação** - Verificações de configuração antes da execução

### Tratamento de Erros
- ✅ **Lógica de retry** - Retries automáticos com backoff exponencial
- ✅ **Rate limiting** - Respeita limites da API
- ✅ **Logging abrangente** - Visibilidade completa da execução
- ✅ **Degradação gradual** - Continua processando outras contas em caso de falha

### Operações de Banco de Dados
- ✅ **Padrão upsert** - Previne duplicatas
- ✅ **Processamento em lote** - Inserções bulk eficientes
- ✅ **Gerenciamento de transações** - Consistência de dados
- ✅ **Connection pooling** - Uso otimizado de recursos

### Pronto para Produção
- ✅ **Type hints** - Melhor suporte de IDE e documentação
- ✅ **Docstrings** - Documentação clara de funções
- ✅ **Logging** - Visibilidade de execução
- ✅ **Estrutura de testes** - Pronto para testes unitários

## 📁 Estrutura do Projeto

```
meta-ads-data-pipeline/
├── dags/
│   ├── meta_graph_api_pipeline.py      # Definição principal da DAG
│   └── grax_midia_facebook_graph_api_new.py  # Legacy (referência)
├── utils/
│   ├── __init__.py
│   ├── database.py                      # Operações de banco de dados
│   └── graph_api.py                     # Cliente Graph API
├── config/
│   ├── __init__.py
│   └── accounts_config.py               # Gerenciamento de contas
├── tests/                               # Testes unitários (a adicionar)
├── docs/
│   ├── ARCHITECTURE.md                  # Arquitetura detalhada
│   └── GIT_WORKFLOW.md                  # Guia de workflow Git
├── .env.example                         # Template de ambiente
├── .gitignore                           # Regras de ignore do Git
├── requirements.txt                     # Dependências Python
└── README.md                            # Este arquivo
```

## 🤝 Contribuindo

Este é um projeto de portfólio, mas sugestões são bem-vindas! Consulte [GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) para diretrizes de contribuição.

## 📚 Documentação Adicional

- [**Detalhes da Arquitetura**](docs/ARCHITECTURE.md) - Arquitetura técnica aprofundada
- [**Workflow Git**](docs/GIT_WORKFLOW.md) - Estratégia de branches e diretrizes de commit
- [**Guia de Setup**](SETUP_GUIDE.md) - Instruções detalhadas de instalação

## 📝 Licença

Este projeto é para fins de demonstração de portfólio.

## 👤 Autor

**Projeto de Portfólio - Engenharia de Dados**

Demonstrando expertise em:
- Orquestração com Apache Airflow
- Integração de APIs e extração de dados
- Arquitetura multi-database
- Desenvolvimento Python pronto para produção
- Boas práticas de engenharia de dados

### Competências Técnicas Demonstradas

- ✅ **Apache Airflow** - Design de DAGs, agendamento, orquestração
- ✅ **Python Avançado** - OOP, type hints, clean code, princípios SOLID
- ✅ **Integração de APIs** - Meta Graph API, paginação, rate limiting
- ✅ **Engenharia de Dados** - ETL, transformação, sincronização
- ✅ **Arquitetura de Dados** - Data lake, analytics layer, multi-database
- ✅ **Boas Práticas** - Documentação, logging, tratamento de erros
- ✅ **DevOps** - Git workflow, Docker, gerenciamento de configuração
- ✅ **Segurança** - Gestão de credenciais, variáveis de ambiente
- ✅ **Performance** - Processamento paralelo, operações em lote

---

## 🎯 Sobre Este Projeto

Este pipeline resolve um problema real de engenharia de dados: **como gerenciar e processar dados de múltiplas contas publicitárias de forma escalável, eficiente e confiável**.

### Problema Resolvido

Empresas que gerenciam múltiplas contas do Meta Business Manager enfrentam desafios como:
- Coleta manual de dados de múltiplas contas
- Rate limits da API
- Inconsistência de dados
- Falta de histórico consolidado
- Processos não escaláveis

### Solução Implementada

Este pipeline automatiza completamente o processo, oferecendo:
- ✅ Extração automática de 10+ contas simultaneamente
- ✅ Rotação inteligente de tokens para otimizar rate limits
- ✅ Dados consolidados em data lake (PostgreSQL)
- ✅ Camada analítica pronta para BI (SQL Server)
- ✅ Agendamento automático (3x por dia)
- ✅ Tratamento robusto de erros e retries
- ✅ Escalável para centenas de contas

### Impacto

- ⏱️ **Economia de tempo**: Horas de trabalho manual → Automático
- 📊 **Qualidade de dados**: Dados consistentes e validados
- 🚀 **Escalabilidade**: Fácil adicionar novas contas
- 🔒 **Confiabilidade**: Retry automático, logging completo
- 📈 **Insights**: Dados prontos para análise e BI

---

**Nota**: Todas as informações sensíveis (credenciais, IDs de contas, nomes de empresas) foram removidas e substituídas por placeholders de variáveis de ambiente. Isso garante que o código possa ser compartilhado com segurança mantendo as melhores práticas de segurança.
# meta-ads-airflow-pipeline
