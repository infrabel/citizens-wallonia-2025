from datetime import datetime

from airflow import DAG, Dataset
from airflow.operators.generic_transfer import GenericTransfer
from airflow.providers.http.operators.http import HttpOperator

with DAG(
    dag_id='extract_punctuality_data',
    start_date=datetime(2025, 1, 1),
    schedule='@daily',
    catchup=False,
    default_args={'owner': 'Joffrey', 'retries': 2},
    description="A basic DAG structure using the DAG class notation.",
    tags=['Bronze', 'Punctuality'],
) as dag:

    query_api = HttpOperator(
        task_id='query_api',
        method='GET',
        endpoint='api/explore/v2.1/catalog/datasets/nationale-stiptheid-per-maand/records',
        http_conn_id='http:infrabel',
        data={
            "select": """
                jaar AS year,
                maand AS month,
                tel AS trains,
                reg AS on_time,
                min_rt AS delay_minutes""",
            "order_by": "month",
            "limit": 100,
            "offset": 10,
        },
        response_filter=lambda response: response.json()["results"],
        log_response=True,
        doc_md="Query Infrabel's OpenData to retrieve punctuality per month data",
    )

    push_to_database = GenericTransfer(
        task_id='push_to_database',
        source_conn_id='duckdb:memory',
        destination_conn_id='postgres:datawarehouse',
        preoperator="""
            CREATE TABLE IF NOT EXISTS infrabel.punctuality (
                year INTEGER,
                month VARCHAR(7) PRIMARY KEY,
                trains INTEGER,
                on_time INTEGER,
                delay_minutes INTEGER
            );
            
            TRUNCATE TABLE infrabel.punctuality;
        """,
        sql="""
            WITH extracted AS (SELECT unnest(from_json(json('{{ ti.xcom_pull(task_ids="query_api") | tojson }}'), '["JSON"]')) AS data)
            SELECT
                (data->'year')::INT as year,
                (data->>'month')::VARCHAR as month,
                (data->'trains')::INT as trains,
                (data->'on_time')::INT as on_time,
                (data->'delay_minutes')::INT as delay_minutes
            FROM extracted
        """,
        destination_table="infrabel.punctuality",
        doc_md="Push data to a Postgres database",
        outlets=[Dataset("infrabel.punctuality")]
    )

    query_api >> push_to_database
