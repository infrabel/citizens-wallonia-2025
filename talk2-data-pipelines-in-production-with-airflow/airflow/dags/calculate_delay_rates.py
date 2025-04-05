from datetime import datetime

from airflow import DAG, Dataset
from airflow.providers.common.sql.operators.sql import BranchSQLOperator, SQLExecuteQueryOperator

outlets = [Dataset("infrabel.calculated_delay")]

with DAG(
    dag_id="calculate_delay_rates",
    start_date=datetime(2025, 1, 1),
    schedule=Dataset("infrabel.punctuality"),
    default_args={'owner': 'Joffrey', 'retries': 2},
    tags=['Silver', 'Punctuality'],
) as dag:

    check_view_exists = BranchSQLOperator(
        task_id='check_view_exists',
        sql="""
            SELECT COUNT(matviewname)
            FROM pg_catalog.pg_matviews
            WHERE schemaname = 'infrabel'
              AND matviewname = 'calculated_delay';
        """,
        conn_id='postgres:datawarehouse',
        follow_task_ids_if_true=["refresh_view"],
        follow_task_ids_if_false=["create_view"],
    )

    create_view = SQLExecuteQueryOperator(
        task_id='create_view',
        sql="""
            CREATE MATERIALIZED VIEW infrabel.calculated_delay AS
            SELECT
                year,
                month,
                trains,
                on_time,
                delay_minutes,
                to_date(month, 'YYYY-MM') AS date,
                to_char(to_date(month, 'YYYY-MM'), 'FMMonth') AS month_name,
                (trains - on_time) AS in_late,
                (on_time::float / trains::float) * 100 AS on_time_rate,
                (delay_minutes::float / (trains - on_time)::float) AS mean_delay_minutes
            FROM infrabel.punctuality
            WITH DATA;
        """,
        conn_id='postgres:datawarehouse',
        outlets=outlets
    )

    refresh_view = SQLExecuteQueryOperator(
        task_id='refresh_view',
        sql="""REFRESH MATERIALIZED VIEW infrabel.calculated_delay;""",
        conn_id='postgres:datawarehouse',
        outlets=outlets
    )

    check_view_exists >> [create_view, refresh_view]