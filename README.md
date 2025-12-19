# Meta Graph API Data Pipeline

[![Apache Airflow](https://img.shields.io/badge/Apache%20Airflow-2.7.3-017CEE?style=flat&logo=Apache%20Airflow&logoColor=white)](https://airflow.apache.org/)
[![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-316192?style=flat&logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![SQL Server](https://img.shields.io/badge/SQL%20Server-CC2927?style=flat&logo=microsoft-sql-server&logoColor=white)](https://www.microsoft.com/sql-server)

A production-ready, scalable Apache Airflow pipeline for extracting, transforming, and loading advertising data from Meta's Graph API (Facebook & Instagram) across multiple Business Manager accounts.

## 🎯 Overview

This project demonstrates a robust data engineering solution for managing advertising data from multiple Meta Business Manager accounts. It showcases:

- **Multi-account orchestration** - Manages 10+ advertising accounts with intelligent token rotation
- **Parallel processing** - Task groups for optimized extraction performance
- **Enterprise-grade architecture** - Separation of concerns, config management, and error handling
- **Database synchronization** - Dual-database strategy (PostgreSQL for data lake, SQL Server for analytics)
- **Production best practices** - Environment-based configuration, comprehensive logging, retry mechanisms

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Apache Airflow DAG                         │
│                                                                 │
│  ┌──────────────┐      ┌──────────────┐                        │
│  │ Task Group 1 │      │ Task Group 2 │                        │
│  │ Accounts 1-5 │  →   │ Accounts 6-10│   →   ┌─────────────┐ │
│  │  (Parallel)  │      │  (Parallel)  │       │ Sync to SQL │ │
│  └──────────────┘      └──────────────┘       └─────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                ↓                                        ↓
      ┌──────────────────┐                    ┌──────────────────┐
      │   PostgreSQL     │                    │   SQL Server     │
      │   (Data Lake)    │    ═══════>        │   (Analytics)    │
      │                  │    Sync Views      │                  │
      │ • Raw ads data   │                    │ • Aggregated data│
      │ • Actions data   │                    │ • Business views │
      │ • Multi-accounts │                    │ • Reporting      │
      └──────────────────┘                    └──────────────────┘
```

### Key Components

1. **DAG Orchestrator** ([meta_graph_api_pipeline.py](dags/meta_graph_api_pipeline.py))
   - Schedules and coordinates all tasks
   - Manages parallel execution with task groups
   - Handles retries and failure scenarios

2. **Graph API Client** ([utils/graph_api.py](utils/graph_api.py))
   - Abstracts Meta Graph API interactions
   - Implements pagination and rate limiting
   - Processes and transforms API responses

3. **Database Manager** ([utils/database.py](utils/database.py))
   - Handles all database operations
   - Implements upsert pattern for data consistency
   - Manages cross-database synchronization

4. **Configuration Layer** ([config/accounts_config.py](config/accounts_config.py))
   - Environment-based configuration
   - Multi-account management with token rotation
   - Validation and error checking

## 🚀 Features

### Multi-Account Management
- **Dynamic account configuration** via environment variables
- **Intelligent token rotation** to distribute API rate limits
- **Parallel processing** with configurable task groups
- **Per-account tables** for data isolation and scalability

### Robust Data Pipeline
- **Incremental loads** with configurable retention period (default: 15 days)
- **Upsert operations** to prevent duplicates
- **Comprehensive error handling** with automatic retries
- **Rate limit management** with exponential backoff

### Enterprise Features
- **Environment-based configuration** - No hardcoded credentials
- **Modular architecture** - Clean separation of concerns
- **Comprehensive logging** - Full visibility into pipeline execution
- **Database synchronization** - Automated data propagation
- **Scalable design** - Easily add new accounts or data sources

## 📋 Prerequisites

- Python 3.8+
- Apache Airflow 2.7.3+
- PostgreSQL 12+
- SQL Server 2019+ (or Azure SQL Database)
- Meta Business Manager account(s) with API access

## 🛠️ Installation

### 1. Clone the Repository

```bash
git clone <repository-url>
cd airflow-graph-api
```

### 2. Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables

Copy the example environment file and configure it with your credentials:

```bash
cp .env.example .env
```

Edit `.env` with your configuration:

```bash
# PostgreSQL Configuration
POSTGRES_HOST=your-postgres-host
POSTGRES_PORT=5432
POSTGRES_USER=your-user
POSTGRES_PASSWORD=your-password
POSTGRES_DATABASE=your-database
POSTGRES_SCHEMA=your-schema

# SQL Server Configuration
SQLSERVER_HOST=your-sqlserver.database.windows.net
SQLSERVER_PORT=1433
SQLSERVER_DATABASE=your-database
SQLSERVER_USER=your-user
SQLSERVER_PASSWORD=your-password
SQLSERVER_SCHEMA=graph

# Meta Graph API Configuration
GRAPH_API_TOKENS=token1,token2,token3
META_ACCOUNTS=account_id_1:bm_01,account_id_2:bm_02,account_id_3:bm_03

# API Configuration
GRAPH_API_VERSION=v19.0
DATA_RETENTION_DAYS=15
```

### 5. Database Setup

Create the required tables in PostgreSQL:

```sql
-- Example schema for ads data
CREATE SCHEMA IF NOT EXISTS your_schema;

CREATE TABLE your_schema.bm_01 (
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

CREATE TABLE your_schema.bm_01_actions (
    account_id VARCHAR(50),
    ad_id VARCHAR(50),
    action_type VARCHAR(100),
    value INTEGER,
    date DATE
);

-- Create views for data consolidation
CREATE VIEW your_schema.vw_graph_ads AS
SELECT * FROM your_schema.bm_01
UNION ALL
SELECT * FROM your_schema.bm_02
-- ... add all your account tables
;
```

### 6. Initialize Airflow

```bash
# Initialize Airflow database
airflow db init

# Create admin user
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com
```

## 🎮 Usage

### Start Airflow

```bash
# Start the web server (default port 8080)
airflow webserver --port 8080

# In another terminal, start the scheduler
airflow scheduler
```

### Access Airflow UI

Navigate to `http://localhost:8080` and login with your credentials.

### Enable the DAG

1. Find the DAG named `meta_graph_api_pipeline`
2. Toggle it to "On"
3. The DAG will run according to schedule: **8:00, 14:00, 20:00 (Mon-Sat)**

### Manual Trigger

You can manually trigger the DAG from the UI or CLI:

```bash
airflow dags trigger meta_graph_api_pipeline
```

## 📊 Data Flow

### Extraction Phase
1. DAG triggers parallel task groups
2. Each task fetches data for one account via Graph API
3. Data includes:
   - Ad performance metrics (spend, clicks, impressions)
   - Campaign information and status
   - Conversion actions and events
4. Data is validated and transformed

### Loading Phase
1. Data is upserted to PostgreSQL account-specific tables
2. Duplicates are prevented using unique_id hash
3. Historical data is maintained based on retention policy

### Synchronization Phase
1. PostgreSQL views aggregate all account data
2. Data is synced to SQL Server for analytics
3. Old records are deleted before inserting new ones
4. Parallel threads optimize large data transfers

## 🔧 Configuration

### Adding New Accounts

Simply update your `.env` file:

```bash
META_ACCOUNTS=existing_accounts,new_account_id:bm_11
GRAPH_API_TOKENS=existing_tokens,new_token
```

The pipeline automatically discovers and processes new accounts.

### Adjusting Schedule

Modify the `SCHEDULE_INTERVAL` in [meta_graph_api_pipeline.py](dags/meta_graph_api_pipeline.py):

```python
SCHEDULE_INTERVAL = "0 8,14,20 * * 1-6"  # Cron format
```

### Customizing Data Retention

Update `.env`:

```bash
DATA_RETENTION_DAYS=30  # Fetch last 30 days instead of 15
```

## 🏆 Best Practices Demonstrated

### Code Organization
- ✅ **Modular design** - Separate modules for API, database, and configuration
- ✅ **DRY principle** - Reusable functions and classes
- ✅ **Clear naming** - Self-documenting code with descriptive names

### Configuration Management
- ✅ **Environment variables** - No hardcoded credentials
- ✅ **`.env.example`** - Template for easy setup
- ✅ **Validation** - Configuration checks before execution

### Error Handling
- ✅ **Retry logic** - Automatic retries with exponential backoff
- ✅ **Rate limiting** - Respects API limits
- ✅ **Comprehensive logging** - Full execution visibility
- ✅ **Graceful degradation** - Continues processing other accounts on failure

### Database Operations
- ✅ **Upsert pattern** - Prevents duplicates
- ✅ **Batch processing** - Efficient bulk inserts
- ✅ **Transaction management** - Data consistency
- ✅ **Connection pooling** - Optimized resource usage

### Production Readiness
- ✅ **Type hints** - Better IDE support and documentation
- ✅ **Docstrings** - Clear function documentation
- ✅ **Logging** - Execution visibility
- ✅ **Testing structure** - Ready for unit tests

## 📁 Project Structure

```
airflow-graph-api/
├── dags/
│   ├── meta_graph_api_pipeline.py      # Main DAG definition
│   └── grax_midia_facebook_graph_api_new.py  # Legacy (for reference)
├── utils/
│   ├── __init__.py
│   ├── database.py                      # Database operations
│   └── graph_api.py                     # Graph API client
├── config/
│   ├── __init__.py
│   └── accounts_config.py               # Account management
├── tests/                               # Unit tests (to be added)
├── docs/
│   ├── ARCHITECTURE.md                  # Detailed architecture
│   └── GIT_WORKFLOW.md                  # Git workflow guide
├── .env.example                         # Environment template
├── .gitignore                           # Git ignore rules
├── requirements.txt                     # Python dependencies
└── README.md                            # This file
```

## 🤝 Contributing

This is a portfolio project, but suggestions are welcome! Please see [GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) for contribution guidelines.

## 📚 Additional Documentation

- [**Architecture Details**](docs/ARCHITECTURE.md) - In-depth technical architecture
- [**Git Workflow**](docs/GIT_WORKFLOW.md) - Branching strategy and commit guidelines

## 📝 License

This project is for portfolio demonstration purposes.

## 👤 Author

**Data Engineering Portfolio Project**

Demonstrating expertise in:
- Apache Airflow orchestration
- API integration and data extraction
- Multi-database architecture
- Production-ready Python development
- Data engineering best practices

---

**Note**: All sensitive information (credentials, account IDs, company names) has been removed and replaced with environment variable placeholders. This ensures the codebase can be safely shared while maintaining security best practices.
# meta-ads-airflow-pipeline
