# Setup Guide - Quick Start

This guide will help you get the Meta Graph API Pipeline up and running quickly.

## Prerequisites Checklist

Before starting, ensure you have:

- [ ] Python 3.8 or higher installed
- [ ] PostgreSQL 12+ database access
- [ ] SQL Server 2019+ or Azure SQL Database access
- [ ] Meta Business Manager account(s)
- [ ] Meta Graph API access tokens
- [ ] Git installed (for version control)

## Step-by-Step Setup

### 1. Clone and Navigate to Project

```bash
git clone <your-repository-url>
cd airflow-graph-api
```

### 2. Create Python Virtual Environment

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**Linux/Mac:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Configure Environment Variables

#### Option A: Using .env file (Recommended)

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your favorite editor
nano .env  # or vim, code, notepad++, etc.
```

Fill in your actual credentials in the `.env` file:

```bash
# PostgreSQL Configuration
POSTGRES_HOST=your-actual-host.com
POSTGRES_PORT=5432
POSTGRES_USER=your_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_DATABASE=your_database
POSTGRES_SCHEMA=your_schema

# SQL Server Configuration
SQLSERVER_HOST=your-server.database.windows.net
SQLSERVER_PORT=1433
SQLSERVER_DATABASE=your_database
SQLSERVER_USER=your_user
SQLSERVER_PASSWORD=your_secure_password
SQLSERVER_SCHEMA=graph

# Meta Graph API Configuration
GRAPH_API_TOKENS=EAAxxxxx...,EAAxxxxx...,EAAxxxxx...
META_ACCOUNTS=123456789:bm_01,987654321:bm_02,111222333:bm_03

# API Configuration
GRAPH_API_VERSION=v19.0
DATA_RETENTION_DAYS=15
```

#### Option B: System Environment Variables

**Windows (PowerShell):**
```powershell
$env:POSTGRES_HOST="your-host"
$env:POSTGRES_USER="your-user"
# ... set all other variables
```

**Linux/Mac:**
```bash
export POSTGRES_HOST="your-host"
export POSTGRES_USER="your-user"
# ... set all other variables
```

### 5. Database Setup

#### PostgreSQL Schema Creation

Connect to your PostgreSQL database and run:

```sql
-- Create schema
CREATE SCHEMA IF NOT EXISTS your_schema;

-- Create account tables (example for bm_01)
CREATE TABLE your_schema.bm_01 (
    unique_id VARCHAR(32) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    account_name VARCHAR(255),
    campaign_id VARCHAR(50),
    campaign_name VARCHAR(255),
    campaign_status VARCHAR(50),
    adset_id VARCHAR(50),
    adset_name VARCHAR(255),
    ad_id VARCHAR(50) NOT NULL,
    ad_name VARCHAR(255),
    objective VARCHAR(100),
    spend DECIMAL(10, 2) DEFAULT 0,
    clicks INTEGER DEFAULT 0,
    inline_link_clicks INTEGER DEFAULT 0,
    impressions INTEGER DEFAULT 0,
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create actions table
CREATE TABLE your_schema.bm_01_actions (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    ad_id VARCHAR(50) NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    value INTEGER DEFAULT 0,
    date DATE NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for performance
CREATE INDEX idx_bm_01_account_date ON your_schema.bm_01(account_id, date);
CREATE INDEX idx_bm_01_campaign ON your_schema.bm_01(campaign_id);
CREATE INDEX idx_bm_01_ad ON your_schema.bm_01(ad_id);

CREATE INDEX idx_bm_01_actions_account_date ON your_schema.bm_01_actions(account_id, date);
CREATE INDEX idx_bm_01_actions_ad_action ON your_schema.bm_01_actions(ad_id, action_type);

-- Repeat for bm_02, bm_03, ... all your accounts
-- Or use a script to generate these dynamically
```

**Helper Script to Generate Tables:**

Save this as `create_tables.sql`:

```sql
-- Run this for each account (bm_01, bm_02, etc.)
DO $$
DECLARE
    table_names TEXT[] := ARRAY['bm_01', 'bm_02', 'bm_03', 'bm_04', 'bm_05',
                                 'bm_06', 'bm_07', 'bm_08', 'bm_09', 'bm_10'];
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY table_names
    LOOP
        -- Create main table
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS your_schema.%I (
                unique_id VARCHAR(32) PRIMARY KEY,
                account_id VARCHAR(50) NOT NULL,
                account_name VARCHAR(255),
                campaign_id VARCHAR(50),
                campaign_name VARCHAR(255),
                campaign_status VARCHAR(50),
                adset_id VARCHAR(50),
                adset_name VARCHAR(255),
                ad_id VARCHAR(50) NOT NULL,
                ad_name VARCHAR(255),
                objective VARCHAR(100),
                spend DECIMAL(10, 2) DEFAULT 0,
                clicks INTEGER DEFAULT 0,
                inline_link_clicks INTEGER DEFAULT 0,
                impressions INTEGER DEFAULT 0,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )', tbl);

        -- Create actions table
        EXECUTE format('
            CREATE TABLE IF NOT EXISTS your_schema.%I (
                id SERIAL PRIMARY KEY,
                account_id VARCHAR(50) NOT NULL,
                ad_id VARCHAR(50) NOT NULL,
                action_type VARCHAR(100) NOT NULL,
                value INTEGER DEFAULT 0,
                date DATE NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )', tbl || '_actions');

        -- Create indexes
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_account_date ON your_schema.%I(account_id, date)', tbl, tbl);
        EXECUTE format('CREATE INDEX IF NOT EXISTS idx_%I_campaign ON your_schema.%I(campaign_id)', tbl, tbl);

        RAISE NOTICE 'Created tables for %', tbl;
    END LOOP;
END $$;
```

Run it:
```bash
psql -h your-host -U your-user -d your-database -f create_tables.sql
```

#### Create Aggregation Views

```sql
-- View to aggregate all account ads data
CREATE OR REPLACE VIEW your_schema.vw_graph_ads AS
SELECT * FROM your_schema.bm_01
UNION ALL
SELECT * FROM your_schema.bm_02
UNION ALL
SELECT * FROM your_schema.bm_03
UNION ALL
SELECT * FROM your_schema.bm_04
UNION ALL
SELECT * FROM your_schema.bm_05
UNION ALL
SELECT * FROM your_schema.bm_06
UNION ALL
SELECT * FROM your_schema.bm_07
UNION ALL
SELECT * FROM your_schema.bm_08
UNION ALL
SELECT * FROM your_schema.bm_09
UNION ALL
SELECT * FROM your_schema.bm_10;

-- View to aggregate all actions data
CREATE OR REPLACE VIEW your_schema.vw_graph_ads_actions AS
SELECT * FROM your_schema.bm_01_actions
UNION ALL
SELECT * FROM your_schema.bm_02_actions
UNION ALL
SELECT * FROM your_schema.bm_03_actions
UNION ALL
SELECT * FROM your_schema.bm_04_actions
UNION ALL
SELECT * FROM your_schema.bm_05_actions
UNION ALL
SELECT * FROM your_schema.bm_06_actions
UNION ALL
SELECT * FROM your_schema.bm_07_actions
UNION ALL
SELECT * FROM your_schema.bm_08_actions
UNION ALL
SELECT * FROM your_schema.bm_09_actions
UNION ALL
SELECT * FROM your_schema.bm_10_actions;
```

#### SQL Server Tables (for sync)

```sql
-- Create schema
CREATE SCHEMA graph;
GO

-- Create tables (same structure as PostgreSQL)
CREATE TABLE graph.graph_ads (
    unique_id VARCHAR(32) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    account_name VARCHAR(255),
    campaign_id VARCHAR(50),
    campaign_name VARCHAR(255),
    campaign_status VARCHAR(50),
    adset_id VARCHAR(50),
    adset_name VARCHAR(255),
    ad_id VARCHAR(50) NOT NULL,
    ad_name VARCHAR(255),
    objective VARCHAR(100),
    spend DECIMAL(10, 2) DEFAULT 0,
    clicks INT DEFAULT 0,
    inline_link_clicks INT DEFAULT 0,
    impressions INT DEFAULT 0,
    date DATE NOT NULL,
    created_at DATETIME DEFAULT GETDATE()
);

CREATE TABLE graph.graph_ads_actions (
    id INT IDENTITY(1,1) PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    ad_id VARCHAR(50) NOT NULL,
    action_type VARCHAR(100) NOT NULL,
    value INT DEFAULT 0,
    date DATE NOT NULL,
    created_at DATETIME DEFAULT GETDATE()
);
GO

-- Create indexes
CREATE INDEX idx_graph_ads_account_date ON graph.graph_ads(account_id, date);
CREATE INDEX idx_graph_ads_campaign ON graph.graph_ads(campaign_id);
GO
```

### 6. Initialize Airflow

```bash
# Set Airflow home (optional, defaults to ~/airflow)
export AIRFLOW_HOME=$(pwd)/airflow_home

# Initialize the database
airflow db init

# Create an admin user
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin
```

### 7. Configure Airflow to Find Your DAGs

Edit `airflow_home/airflow.cfg`:

```ini
[core]
dags_folder = /full/path/to/airflow-graph-api/dags
load_examples = False
```

Or set via environment variable:

```bash
export AIRFLOW__CORE__DAGS_FOLDER=/full/path/to/airflow-graph-api/dags
```

### 8. Start Airflow

**Terminal 1 - Start Web Server:**
```bash
airflow webserver --port 8080
```

**Terminal 2 - Start Scheduler:**
```bash
airflow scheduler
```

### 9. Access Airflow UI

1. Open browser: http://localhost:8080
2. Login with credentials (admin/admin)
3. Find DAG: `meta_graph_api_pipeline`
4. Toggle it to "On"
5. Click "Trigger DAG" to run manually

### 10. Monitor Execution

- Check "Graph View" to see task progress
- View "Logs" for each task to see detailed output
- Monitor database to see data being inserted

## Validation Checklist

After setup, verify:

- [ ] Airflow UI is accessible
- [ ] DAG appears in the list
- [ ] No import errors in DAG
- [ ] Environment variables are loaded
- [ ] Database connections work
- [ ] Manual trigger succeeds
- [ ] Data appears in PostgreSQL tables
- [ ] Data syncs to SQL Server

## Common Issues & Solutions

### Issue: "ModuleNotFoundError: No module named 'dotenv'"

**Solution:**
```bash
pip install python-dotenv
```

### Issue: "psycopg2 installation error"

**Solution:**
```bash
# Use binary version
pip install psycopg2-binary
```

### Issue: "Can't connect to PostgreSQL"

**Solution:**
- Check firewall rules
- Verify host, port, credentials
- Test connection manually:
```bash
psql -h your-host -U your-user -d your-database
```

### Issue: "DAG not appearing in Airflow"

**Solution:**
- Check AIRFLOW_HOME and dags_folder path
- Check for Python syntax errors in DAG file
- Restart scheduler
- Check scheduler logs

### Issue: "Import errors in DAG"

**Solution:**
- Ensure virtual environment is activated
- Verify all dependencies are installed
- Check Python path includes project root

### Issue: "API rate limit errors"

**Solution:**
- Add more tokens to `GRAPH_API_TOKENS`
- Increase `RATE_LIMIT_SLEEP_SECONDS`
- Reduce number of parallel tasks

## Next Steps

After successful setup:

1. **Test with one account** - Start small, verify it works
2. **Add more accounts** - Update `.env` with additional accounts
3. **Schedule regular runs** - Let the DAG run on schedule
4. **Monitor performance** - Check execution times, optimize if needed
5. **Set up alerts** - Configure email notifications for failures

## Getting Help

- Check logs in Airflow UI
- Review [ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical details
- See [README.md](README.md) for feature overview
- Check [GIT_WORKFLOW.md](docs/GIT_WORKFLOW.md) for development guidelines

## Quick Test Command

Test the pipeline manually without Airflow:

```bash
python -c "
import os
from dotenv import load_dotenv
load_dotenv()

from config.accounts_config import AccountsConfig
from utils.database import DatabaseManager
from utils.graph_api import extract_meta_ads_data

# Initialize
config = AccountsConfig()
db_manager = DatabaseManager()

# Test first account
account, token = config.get_account_with_token(0)
print(f'Testing account: {account}')

extract_meta_ads_data(
    account_id=account['account_id'],
    access_token=token,
    table_name=account['table'],
    actions_table_name=f\"{account['table']}_actions\",
    db_manager=db_manager
)
"
```

If this runs successfully, your setup is complete! 🎉
