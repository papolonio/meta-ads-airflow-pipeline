# Architecture Documentation

## Table of Contents
- [System Overview](#system-overview)
- [Component Architecture](#component-architecture)
- [Data Flow](#data-flow)
- [Database Schema](#database-schema)
- [API Integration](#api-integration)
- [Performance Optimization](#performance-optimization)
- [Error Handling & Resilience](#error-handling--resilience)
- [Scalability Considerations](#scalability-considerations)

---

## System Overview

This pipeline is a production-grade data engineering solution designed to extract advertising data from Meta's Graph API across multiple Business Manager accounts, process it, and store it in a dual-database architecture for both data warehousing and analytics.

### High-Level Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                           ORCHESTRATION LAYER                          │
│                        (Apache Airflow Scheduler)                      │
│                                                                        │
│  ┌──────────────────────────────────────────────────────────────────┐ │
│  │  DAG: meta_graph_api_pipeline                                    │ │
│  │  Schedule: 3x daily (8am, 2pm, 8pm) Mon-Sat                      │ │
│  │                                                                  │ │
│  │  ┌────────────────┐    ┌────────────────┐    ┌───────────────┐ │ │
│  │  │  Task Group 1  │───>│  Task Group 2  │───>│  Sync to SQL  │ │ │
│  │  │  (Accounts 1-5)│    │  (Accounts 6-10)│   │  Server       │ │ │
│  │  └────────────────┘    └────────────────┘    └───────────────┘ │ │
│  └──────────────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────┘
                     ↓                                    ↓
         ┌──────────────────────┐           ┌──────────────────────────┐
         │   EXTRACTION LAYER   │           │   INTEGRATION LAYER      │
         │  (Graph API Client)  │           │  (Database Sync)         │
         │                      │           │                          │
         │  • Rate limiting     │           │  • Cross-DB sync         │
         │  • Pagination        │           │  • Schema mapping        │
         │  • Token rotation    │           │  • Parallel inserts      │
         │  • Error retry       │           │  • Data validation       │
         └──────────────────────┘           └──────────────────────────┘
                     ↓                                    ↓
         ┌──────────────────────┐           ┌──────────────────────────┐
         │   STORAGE LAYER 1    │           │   STORAGE LAYER 2        │
         │   (PostgreSQL)       │  ══════>  │   (SQL Server)           │
         │                      │  Sync     │                          │
         │  • Raw data storage  │           │  • Analytics layer       │
         │  • Account isolation │           │  • Business reporting    │
         │  • Aggregation views │           │  • BI tool integration   │
         └──────────────────────┘           └──────────────────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Orchestration** | Apache Airflow 2.7.3 | DAG scheduling, task management, monitoring |
| **Programming** | Python 3.8+ | Pipeline logic, data transformation |
| **API Client** | Requests + Meta Graph API | Data extraction from Meta platforms |
| **Data Processing** | Pandas | Data transformation and manipulation |
| **Primary Storage** | PostgreSQL 12+ | Data lake, raw storage |
| **Analytics Storage** | SQL Server 2019+ | Business intelligence, reporting |
| **Database ORM** | SQLAlchemy 2.0+ | Database abstraction, connection pooling |
| **Config Management** | python-dotenv | Environment variable management |

---

## Component Architecture

### 1. DAG Orchestrator (`dags/meta_graph_api_pipeline.py`)

**Responsibility**: Workflow orchestration and task coordination

**Key Features**:
- Dynamic task generation based on configuration
- Task grouping for parallel execution
- Dependency management (sequential groups, final sync)
- Retry logic and failure handling
- Environment-based configuration loading

**Design Patterns**:
- **Factory Pattern**: Dynamic task creation based on account configuration
- **Builder Pattern**: DAG construction with default arguments
- **Dependency Injection**: DatabaseManager and config injected into tasks

```python
# Pseudo-code structure
DAG Definition
├── Load Environment Config
├── Initialize AccountsConfig
├── Create Task Groups (parallel processing)
│   ├── Group 1: Accounts 1-5
│   │   ├── Extract Account 1 (with Token rotation)
│   │   ├── Extract Account 2
│   │   └── ...
│   └── Group 2: Accounts 6-10
│       ├── Extract Account 6
│       └── ...
└── Sync Task (after all extractions)
```

### 2. Graph API Client (`utils/graph_api.py`)

**Responsibility**: Meta Graph API integration and data extraction

**Components**:

#### `GraphAPIConfig`
- Centralized API configuration
- Environment-based settings
- Default value management

#### `GraphAPIClient`
- API authentication and requests
- Pagination handling
- Rate limit management
- Time range calculation
- Data retrieval (insights & campaigns)

#### `GraphAPIDataProcessor`
- Data transformation
- Unique ID generation (MD5 hashing)
- DataFrame construction
- Data merging and aggregation

**Key Algorithms**:

```python
# Pagination Algorithm
while has_next_page:
    response = make_api_request(url, params)

    if rate_limit_error:
        sleep(configured_duration)
        retry_request()

    data.extend(response.data)
    url = response.paging.next
```

**Error Handling**:
- HTTP error codes handling
- Rate limit detection and backoff
- Network timeout management
- Partial data recovery

### 3. Database Manager (`utils/database.py`)

**Responsibility**: Database operations and data persistence

**Components**:

#### `DatabaseConfig`
- Environment variable loading
- Connection string generation
- Multi-database support

#### `DatabaseManager`
- Connection pooling
- Lazy engine initialization
- CRUD operations
- Cross-database synchronization

**Key Operations**:

##### Upsert Strategy
```
1. Calculate date range from DataFrame
2. BEGIN TRANSACTION
3. DELETE existing records in date range
4. INSERT new records in batches (chunksize=1000)
5. COMMIT TRANSACTION
```

##### Sync Strategy (PostgreSQL → SQL Server)
```
1. Query PostgreSQL view (filtered by retention days)
2. Preprocess data (JSON serialization)
3. Validate columns against target schema
4. DELETE old data from SQL Server
5. Parallel INSERT using ThreadPoolExecutor
6. Commit changes
```

**Performance Optimizations**:
- `fast_executemany` enabled for SQL Server
- Batch inserts (chunksize=1000)
- Multi-threaded inserts (max 8 threads)
- Connection pooling via SQLAlchemy

### 4. Configuration Layer (`config/accounts_config.py`)

**Responsibility**: Account management and configuration validation

**Features**:
- Environment-based account loading
- Token rotation logic
- Account grouping for parallel processing
- Configuration validation
- Duplicate detection (accounts and tables)

**Token Rotation Algorithm**:
```python
# Distribute API calls across tokens to avoid rate limits
token_index = account_index % total_tokens
selected_token = tokens[token_index]
```

---

## Data Flow

### Detailed Extraction Flow

```
┌─────────────┐
│ Airflow DAG │
│   Trigger   │
└──────┬──────┘
       │
       ├─── Load .env configuration
       │
       ├─── Initialize AccountsConfig
       │         │
       │         ├─── Parse META_ACCOUNTS
       │         ├─── Parse GRAPH_API_TOKENS
       │         └─── Validate configuration
       │
       ├─── Create Task Groups
       │
       ├─── Execute Group 1 (Parallel)
       │         │
       │         ├─── Task: Extract Account 1
       │         │       │
       │         │       ├─── GraphAPIClient.get_insights()
       │         │       │       │
       │         │       │       ├─── API Request (paginated)
       │         │       │       ├─── Rate limit handling
       │         │       │       └─── Return raw JSON data
       │         │       │
       │         │       ├─── GraphAPIClient.get_campaigns()
       │         │       │
       │         │       ├─── GraphAPIDataProcessor.process_insights_data()
       │         │       │       │
       │         │       │       ├─── Parse insights → DataFrame
       │         │       │       ├─── Parse actions → DataFrame
       │         │       │       ├─── Merge with campaign data
       │         │       │       └─── Generate unique_id hash
       │         │       │
       │         │       └─── DatabaseManager.upsert_dataframe()
       │         │               │
       │         │               ├─── Calculate date range
       │         │               ├─── DELETE old records
       │         │               └─── INSERT new records (batched)
       │         │
       │         ├─── Task: Extract Account 2
       │         └─── ... (parallel execution)
       │
       ├─── Execute Group 2 (Parallel)
       │
       └─── Execute Sync Task
                 │
                 ├─── Read PostgreSQL views
                 ├─── Preprocess data
                 ├─── Validate SQL Server schema
                 ├─── DELETE old SQL Server data
                 └─── INSERT new data (multi-threaded)
```

### Data Transformation Pipeline

#### Stage 1: Raw API Response
```json
{
  "ad_id": "123456",
  "ad_name": "Campaign Ad 1",
  "spend": "150.50",
  "clicks": "450",
  "actions": [
    {"action_type": "link_click", "value": "120"},
    {"action_type": "purchase", "value": "5"}
  ]
}
```

#### Stage 2: Processed DataFrame (Ads)
```
| unique_id | account_id | ad_id  | ad_name       | spend  | clicks | date       |
|-----------|------------|--------|---------------|--------|--------|------------|
| abc123... | 123456789  | 123456 | Campaign Ad 1 | 150.50 | 450    | 2024-01-15 |
```

#### Stage 3: Processed DataFrame (Actions)
```
| account_id | ad_id  | action_type | value | date       |
|------------|--------|-------------|-------|------------|
| 123456789  | 123456 | link_click  | 120   | 2024-01-15 |
| 123456789  | 123456 | purchase    | 5     | 2024-01-15 |
```

#### Stage 4: Database Storage (PostgreSQL)
```sql
-- Table: bm_01
INSERT INTO schema.bm_01 (unique_id, account_id, ad_id, ...) VALUES (...);

-- Table: bm_01_actions
INSERT INTO schema.bm_01_actions (account_id, ad_id, action_type, ...) VALUES (...);
```

#### Stage 5: Aggregated View (PostgreSQL)
```sql
CREATE VIEW schema.vw_graph_ads AS
SELECT * FROM schema.bm_01
UNION ALL
SELECT * FROM schema.bm_02
UNION ALL
-- ... all account tables
;
```

#### Stage 6: Analytics Storage (SQL Server)
```sql
-- Table: graph.graph_ads
-- Synced from PostgreSQL view
-- Used for BI tools and reporting
```

---

## Database Schema

### PostgreSQL Schema

#### Account Tables (e.g., `bm_01`, `bm_02`, ...)

```sql
CREATE TABLE schema.bm_01 (
    unique_id VARCHAR(32) PRIMARY KEY,          -- MD5 hash of row data
    account_id VARCHAR(50) NOT NULL,            -- Meta account ID
    account_name VARCHAR(255),                  -- Account name
    campaign_id VARCHAR(50),                    -- Campaign ID
    campaign_name VARCHAR(255),                 -- Campaign name
    campaign_status VARCHAR(50),                -- ACTIVE, PAUSED, etc.
    adset_id VARCHAR(50),                       -- Adset ID
    adset_name VARCHAR(255),                    -- Adset name
    ad_id VARCHAR(50) NOT NULL,                 -- Ad ID
    ad_name VARCHAR(255),                       -- Ad name
    objective VARCHAR(100),                     -- OUTCOME_TRAFFIC, etc.
    spend DECIMAL(10, 2) DEFAULT 0,             -- Amount spent
    clicks INTEGER DEFAULT 0,                   -- Total clicks
    inline_link_clicks INTEGER DEFAULT 0,       -- Link clicks
    impressions INTEGER DEFAULT 0,              -- Total impressions
    date DATE NOT NULL,                         -- Performance date

    INDEX idx_account_date (account_id, date),
    INDEX idx_campaign (campaign_id),
    INDEX idx_ad (ad_id)
);
```

#### Actions Tables (e.g., `bm_01_actions`, ...)

```sql
CREATE TABLE schema.bm_01_actions (
    id SERIAL PRIMARY KEY,
    account_id VARCHAR(50) NOT NULL,
    ad_id VARCHAR(50) NOT NULL,
    action_type VARCHAR(100) NOT NULL,          -- link_click, purchase, etc.
    value INTEGER DEFAULT 0,                    -- Count of actions
    date DATE NOT NULL,

    INDEX idx_account_date (account_id, date),
    INDEX idx_ad_action (ad_id, action_type)
);
```

#### Aggregation Views

```sql
-- Consolidated view of all accounts
CREATE VIEW schema.vw_graph_ads AS
SELECT * FROM schema.bm_01
UNION ALL
SELECT * FROM schema.bm_02
UNION ALL
-- ... all accounts
;

-- Consolidated actions view
CREATE VIEW schema.vw_graph_ads_actions AS
SELECT * FROM schema.bm_01_actions
UNION ALL
SELECT * FROM schema.bm_02_actions
UNION ALL
-- ... all accounts
;
```

### SQL Server Schema

```sql
-- Mirror of PostgreSQL aggregated views
-- Used for reporting and BI tools

CREATE TABLE graph.graph_ads (
    -- Same structure as PostgreSQL bm_XX tables
    -- Populated via sync task
);

CREATE TABLE graph.graph_ads_actions (
    -- Same structure as PostgreSQL bm_XX_actions tables
    -- Populated via sync task
);
```

---

## API Integration

### Meta Graph API Specifications

**API Version**: v19.0
**Authentication**: Access Token (OAuth 2.0)
**Base URL**: `https://graph.facebook.com/v19.0/`

### Endpoints Used

#### 1. Insights Endpoint
```
GET /act_{account_id}/insights
```

**Parameters**:
- `time_increment`: 1 (daily granularity)
- `time_range`: {"since": "YYYY-MM-DD", "until": "YYYY-MM-DD"}
- `level`: "ad"
- `fields`: ad_name, ad_id, spend, clicks, impressions, actions, ...
- `access_token`: {token}

**Response Structure**:
```json
{
  "data": [
    {
      "ad_id": "123",
      "ad_name": "Ad Name",
      "spend": "100.50",
      "actions": [...]
    }
  ],
  "paging": {
    "next": "https://..."
  }
}
```

#### 2. Campaigns Endpoint
```
GET /act_{account_id}/campaigns
```

**Parameters**:
- `fields`: id, name, status, start_time
- `access_token`: {token}

### Rate Limiting Strategy

**Meta Rate Limits**:
- 200 calls per hour per access token
- Errors return HTTP 400 with "too many calls" message

**Our Strategy**:
1. **Token Rotation**: Distribute calls across multiple tokens
2. **Exponential Backoff**: Wait 60s when rate limit hit
3. **Graceful Retry**: Retry failed requests automatically
4. **Parallel Execution**: Process accounts in parallel groups

---

## Performance Optimization

### 1. Parallel Processing

**Task Groups**: Accounts split into groups that run in parallel
```python
# Group 1: Accounts 1-5 (parallel)
# Group 2: Accounts 6-10 (parallel)
# Groups run sequentially to manage total API load
```

**Benefits**:
- Reduces total execution time by ~50%
- Balances API rate limits across tokens
- Allows partial success (some accounts can fail without blocking others)

### 2. Database Optimizations

**PostgreSQL**:
- Batch inserts (chunksize=1000)
- SQLAlchemy connection pooling
- Index on frequently queried columns
- VACUUM and ANALYZE scheduled separately

**SQL Server**:
- `fast_executemany` enabled (pyodbc)
- Multi-threaded inserts (8 threads)
- Bulk insert operations
- Minimal logging during inserts

### 3. Data Processing

**Memory Management**:
- Process data in chunks to avoid memory overflow
- Stream large API responses
- Clear DataFrames after insertion

**Computation**:
- Vectorized operations (Pandas)
- Minimal in-memory transformations
- Lazy evaluation where possible

---

## Error Handling & Resilience

### Retry Strategy

**Airflow Level**:
```python
default_args = {
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}
```

**API Level**:
- Automatic retry on rate limit (60s wait)
- Continue on network errors (log and skip)
- Partial data recovery (process successful pages)

### Failure Scenarios

| Scenario | Handling |
|----------|----------|
| **API token invalid** | Log error, skip account, alert team |
| **Rate limit exceeded** | Wait 60s, retry request |
| **Network timeout** | Retry up to 2 times, then fail task |
| **Database connection lost** | SQLAlchemy auto-reconnect |
| **Partial data** | Process available data, log missing ranges |
| **Task failure** | Airflow retries, other accounts continue |

### Monitoring

**Logs**:
- Detailed logging at each stage
- API response times tracked
- Record counts logged
- Error stack traces captured

**Airflow UI**:
- Task duration monitoring
- Success/failure visualization
- Log aggregation
- Email alerts on failure (configurable)

---

## Scalability Considerations

### Current Scale
- **10 accounts** managed
- **~5 tokens** in rotation
- **15 days** of data per run
- **~10,000-50,000 rows** per account per run
- **3 executions** per day

### Scaling Strategies

#### Horizontal Scaling
1. **Add more accounts**: Simply update `.env` configuration
2. **Increase task groups**: Split accounts into more parallel groups
3. **Distribute across workers**: Deploy multiple Airflow workers

#### Vertical Scaling
1. **Increase database resources**: Scale PostgreSQL/SQL Server
2. **Optimize batch sizes**: Tune chunksize based on data volume
3. **Increase thread count**: Adjust max_threads for SQL Server sync

#### Future Enhancements
- [ ] Implement incremental loads (only fetch new data)
- [ ] Add data quality checks and validation
- [ ] Implement data lineage tracking
- [ ] Add alerting and monitoring (Prometheus/Grafana)
- [ ] Create data catalog and documentation
- [ ] Implement CDC (Change Data Capture) for real-time sync
- [ ] Add data retention policies and archiving

---

## Security Considerations

### Credentials Management
✅ **Environment variables** - No hardcoded secrets
✅ **`.env` excluded from Git** - Via .gitignore
✅ **`.env.example` provided** - Template without secrets
✅ **Database passwords encrypted** - In production environment

### API Security
✅ **Token rotation** - Reduces single point of failure
✅ **HTTPS only** - All API calls encrypted
✅ **Token expiration handling** - Manual refresh process documented

### Database Security
✅ **Least privilege access** - Service accounts with minimal permissions
✅ **SSL/TLS connections** - Required for SQL Server
✅ **Network isolation** - Databases in private network (production)

---

## Maintenance & Operations

### Daily Operations
- Monitor Airflow UI for task failures
- Check database disk space usage
- Review API rate limit usage

### Weekly Operations
- Review execution times for performance degradation
- Check database vacuum/analyze schedules
- Validate data quality

### Monthly Operations
- Review and rotate API tokens if needed
- Database performance tuning
- Update dependencies (security patches)

### Backup Strategy
- **PostgreSQL**: Daily full backups + WAL archiving
- **SQL Server**: Daily differential backups
- **Code**: Version controlled in Git
- **Configuration**: Backed up separately (encrypted)

---

**Document Version**: 1.0
**Last Updated**: 2024
**Maintained By**: Data Engineering Team
