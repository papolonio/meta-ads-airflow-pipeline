import os
import json
from typing import List, Dict
from datetime import datetime, timedelta
from urllib.parse import quote_plus

import pandas as pd
from sqlalchemy import create_engine, text, event, Engine
from concurrent.futures import ThreadPoolExecutor


class DatabaseConfig:
    """Database configuration from environment variables."""

    def __init__(self):
        self.postgres_host = os.getenv('POSTGRES_HOST')
        self.postgres_port = os.getenv('POSTGRES_PORT', '5432')
        self.postgres_user = os.getenv('POSTGRES_USER')
        self.postgres_password = os.getenv('POSTGRES_PASSWORD')
        self.postgres_database = os.getenv('POSTGRES_DATABASE')
        self.postgres_schema = os.getenv('POSTGRES_SCHEMA', 'public')

        self.sqlserver_host = os.getenv('SQLSERVER_HOST')
        self.sqlserver_port = os.getenv('SQLSERVER_PORT', '1433')
        self.sqlserver_database = os.getenv('SQLSERVER_DATABASE')
        self.sqlserver_user = os.getenv('SQLSERVER_USER')
        self.sqlserver_password = os.getenv('SQLSERVER_PASSWORD')
        self.sqlserver_schema = os.getenv('SQLSERVER_SCHEMA', 'dbo')

    def get_postgres_connection_string(self) -> str:
        """Build PostgreSQL connection string."""
        return (
            f"postgresql+psycopg2://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_database}"
        )

    def get_sqlserver_connection_string(self) -> str:
        """Build SQL Server connection string."""
        odbc_string = (
            f'Driver={{ODBC Driver 18 for SQL Server}};'
            f'Server=tcp:{self.sqlserver_host},{self.sqlserver_port};'
            f'Database={self.sqlserver_database};'
            f'Uid={self.sqlserver_user};'
            f'Pwd={self.sqlserver_password};'
            f'Encrypt=yes;'
            f'TrustServerCertificate=no;'
            f'Connection Timeout=30;'
        )
        return f"mssql+pyodbc:///?odbc_connect={quote_plus(odbc_string)}"


class DatabaseManager:
    """Manages database connections and operations."""

    def __init__(self, config: DatabaseConfig = None):
        self.config = config or DatabaseConfig()
        self._postgres_engine = None
        self._sqlserver_engine = None

    @property
    def postgres_engine(self) -> Engine:
        """Get or create PostgreSQL engine."""
        if self._postgres_engine is None:
            self._postgres_engine = create_engine(
                self.config.get_postgres_connection_string()
            )
        return self._postgres_engine

    @property
    def sqlserver_engine(self) -> Engine:
        """Get or create SQL Server engine with fast_executemany enabled."""
        if self._sqlserver_engine is None:
            self._sqlserver_engine = create_engine(
                self.config.get_sqlserver_connection_string()
            )
            # Enable fast_executemany for better performance
            @event.listens_for(self._sqlserver_engine, "before_cursor_execute")
            def enable_fast_executemany(conn, cursor, statement, parameters, context, executemany):
                if executemany:
                    cursor.fast_executemany = True

        return self._sqlserver_engine

    def upsert_dataframe(
        self,
        df: pd.DataFrame,
        table_name: str,
        date_column: str,
        schema: str = None
    ) -> None:
        """
        Upsert DataFrame to PostgreSQL using delete-insert pattern.

        Args:
            df: DataFrame to insert
            table_name: Target table name
            date_column: Column name containing dates for deletion range
            schema: Database schema name (default: from config)
        """
        if df.empty:
            print(f"⚠️ DataFrame empty. Nothing to insert into {schema}.{table_name}")
            return

        schema = schema or self.config.postgres_schema
        min_date = df[date_column].min()
        max_date = df[date_column].max()

        print(f"🗑️ Deleting from {schema}.{table_name} between {min_date} and {max_date}...")

        delete_query = text(f"""
            DELETE FROM {schema}.{table_name}
            WHERE {date_column} BETWEEN :min_date AND :max_date
        """)

        with self.postgres_engine.begin() as conn:
            conn.execute(delete_query, {"min_date": min_date, "max_date": max_date})

        print(f"🚀 Inserting {len(df)} records into {schema}.{table_name}...")

        df.to_sql(
            name=table_name,
            con=self.postgres_engine,
            schema=schema,
            if_exists='append',
            index=False,
            method='multi',
            chunksize=1000
        )

        print(f"✅ {len(df)} records inserted into {schema}.{table_name}")

    def sync_postgres_to_sqlserver(
        self,
        view_name: str,
        target_table: str,
        date_column: str = 'date',
        days: int = 15,
        source_schema: str = None,
        target_schema: str = None,
        chunksize: int = 1000,
        max_threads: int = 8
    ) -> None:
        """
        Sync data from PostgreSQL view to SQL Server table.

        Args:
            view_name: Source view name in PostgreSQL
            target_table: Target table name in SQL Server
            date_column: Date column for filtering
            days: Number of days to sync
            source_schema: PostgreSQL schema
            target_schema: SQL Server schema
            chunksize: Batch size for inserts
            max_threads: Maximum parallel threads
        """
        source_schema = source_schema or self.config.postgres_schema
        target_schema = target_schema or self.config.sqlserver_schema

        print(f"\n🔄 Starting sync: {source_schema}.{view_name} ➝ {target_schema}.{target_table}")

        # Read from PostgreSQL
        start_date = (datetime.now() - timedelta(days=days)).date()
        query = f"""
            SELECT * FROM {source_schema}.{view_name}
            WHERE {date_column} >= '{start_date}'
        """

        df = pd.read_sql(query, self.postgres_engine)
        print(f"📥 Read {len(df)} records from {source_schema}.{view_name}")

        if df.empty:
            print(f"⚠️ No data found for {view_name}")
            return

        # Preprocess DataFrame
        df = self._preprocess_dataframe(df)
        df[date_column] = pd.to_datetime(df[date_column]).dt.date

        # Get and validate columns
        sql_columns = self._get_sqlserver_columns(target_schema, target_table)
        df = df[[col for col in df.columns if col in sql_columns]]

        # Delete old data from SQL Server
        end_date = datetime.now().date()
        with self.sqlserver_engine.begin() as conn:
            conn.execute(
                text(f"""
                    DELETE FROM {target_schema}.{target_table}
                    WHERE {date_column} BETWEEN :start AND :end
                """),
                {"start": start_date, "end": end_date}
            )
            print(f"🗑️ Deleted data from {target_schema}.{target_table} between {start_date} and {end_date}")

        # Insert in chunks using ThreadPoolExecutor
        chunks = [df.iloc[i:i+chunksize] for i in range(0, len(df), chunksize)]

        def insert_chunk(chunk):
            try:
                chunk.to_sql(
                    target_table,
                    self.sqlserver_engine,
                    schema=target_schema,
                    if_exists='append',
                    index=False
                )
            except Exception as e:
                print(f"⚠️ Error inserting chunk: {e}")

        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            list(executor.map(insert_chunk, chunks))

        print(f"✅ Inserted {len(df)} records into {target_schema}.{target_table}")

    def _preprocess_dataframe(self, df: pd.DataFrame) -> pd.DataFrame:
        """Preprocess DataFrame for SQL Server compatibility."""
        df = df.copy()
        for col in df.columns:
            if df[col].apply(lambda x: isinstance(x, (dict, list))).any():
                df[col] = df[col].apply(
                    lambda x: json.dumps(x) if isinstance(x, (dict, list)) else x
                )
        return df

    def _get_sqlserver_columns(self, schema: str, table: str) -> List[str]:
        """Get column names from SQL Server table."""
        query = f"""
            SELECT COLUMN_NAME
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = '{schema}' AND TABLE_NAME = '{table}'
        """
        with self.sqlserver_engine.connect() as conn:
            result = conn.execute(text(query))
            return [row[0] for row in result]

    def dispose(self):
        """Dispose all database connections."""
        if self._postgres_engine:
            self._postgres_engine.dispose()
        if self._sqlserver_engine:
            self._sqlserver_engine.dispose()
