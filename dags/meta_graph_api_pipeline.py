import os
import sys
from datetime import timedelta
from pathlib import Path

from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from airflow.utils.task_group import TaskGroup
from airflow.utils.dates import days_ago
from airflow.utils.trigger_rule import TriggerRule
from dotenv import load_dotenv

# Add project root to path for imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Load environment variables
env_path = project_root / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Import project modules
from utils.database import DatabaseManager, DatabaseConfig
from utils.graph_api import extract_meta_ads_data
from config.accounts_config import AccountsConfig


# ============================================================================
# DAG Configuration
# ============================================================================

DAG_ID = 'meta_graph_api_pipeline'
SCHEDULE_INTERVAL = "0 8,14,20 * * 1-6"  # 8am, 2pm, 8pm Mon-Sat
MAX_ACTIVE_RUNS = 1
RETRIES = int(os.getenv('AIRFLOW_RETRIES', '2'))
RETRY_DELAY_MINUTES = int(os.getenv('AIRFLOW_RETRY_DELAY_MINUTES', '5'))
OWNER = os.getenv('AIRFLOW_OWNER', 'data-engineering')


# ============================================================================
# Task Functions
# ============================================================================

def extract_account_data(account_id: str, token: str, table_name: str, **kwargs) -> None:
    """
    Extract data for a single Meta Ads account.

    Args:
        account_id: Meta Ads account ID
        token: Graph API access token
        table_name: Target table name for ads data
        **kwargs: Airflow context (automatically provided)
    """
    db_config = DatabaseConfig()
    db_manager = DatabaseManager(db_config)

    try:
        extract_meta_ads_data(
            account_id=account_id,
            access_token=token,
            table_name=table_name,
            actions_table_name=f"{table_name}_actions",
            db_manager=db_manager,
            schema=db_config.postgres_schema
        )
    finally:
        db_manager.dispose()


def sync_to_sqlserver(**kwargs) -> None:
    """
    Sync aggregated data from PostgreSQL views to SQL Server tables.

    This task runs after all account extractions are complete and syncs
    the consolidated data to SQL Server for reporting and analytics.

    Args:
        **kwargs: Airflow context (automatically provided)
    """
    db_config = DatabaseConfig()
    db_manager = DatabaseManager(db_config)

    # Tables to sync: view_name -> target_table
    sync_mappings = [
        {"view": "vw_graph_ads", "table": "graph_ads"},
        {"view": "vw_graph_ads_actions", "table": "graph_ads_actions"},
    ]

    try:
        for mapping in sync_mappings:
            db_manager.sync_postgres_to_sqlserver(
                view_name=mapping['view'],
                target_table=mapping['table'],
                source_schema=db_config.postgres_schema,
                target_schema=db_config.sqlserver_schema
            )
    finally:
        db_manager.dispose()


# ============================================================================
# DAG Definition
# ============================================================================

default_args = {
    'owner': OWNER,
    'retries': RETRIES,
    'retry_delay': timedelta(minutes=RETRY_DELAY_MINUTES),
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
}

with DAG(
    dag_id=DAG_ID,
    start_date=days_ago(1),
    schedule_interval=SCHEDULE_INTERVAL,
    catchup=False,
    default_args=default_args,
    tags=['meta-ads', 'graph-api', 'data-pipeline', 'multi-account'],
    max_active_runs=MAX_ACTIVE_RUNS,
    description='Extract Meta Ads data from Graph API for multiple accounts',
) as dag:

    # Initialize accounts configuration
    accounts_config = AccountsConfig()
    accounts_config.validate_configuration()

    # Split accounts into groups for parallel processing
    account_groups = accounts_config.split_accounts_into_groups(num_groups=2)

    task_groups = []

    # Create task groups for each account group
    for group_idx, accounts_group in enumerate(account_groups, start=1):
        group_id = f"accounts_group_{group_idx}"

        with TaskGroup(
            group_id=group_id,
            tooltip=f"Process accounts {(group_idx-1)*len(accounts_group)+1} to {group_idx*len(accounts_group)}"
        ) as task_group:

            for account in accounts_group:
                # Calculate global account index for token rotation
                global_idx = accounts_config.accounts.index(account)
                _, token = accounts_config.get_account_with_token(global_idx)

                # Create extraction task for this account
                extract_task = PythonOperator(
                    task_id=f"extract_{account['table']}",
                    python_callable=extract_account_data,
                    op_kwargs={
                        'account_id': account['account_id'],
                        'token': token,
                        'table_name': account['table']
                    },
                    trigger_rule=TriggerRule.ALL_DONE
                )

        task_groups.append(task_group)

    # Create SQL Server sync task
    sync_task = PythonOperator(
        task_id='sync_to_sqlserver',
        python_callable=sync_to_sqlserver,
        trigger_rule=TriggerRule.ALL_DONE
    )

    # Set task dependencies
    # Groups run sequentially, then sync runs after all groups complete
    if len(task_groups) > 1:
        for i in range(len(task_groups) - 1):
            task_groups[i] >> task_groups[i + 1]

    task_groups[-1] >> sync_task
