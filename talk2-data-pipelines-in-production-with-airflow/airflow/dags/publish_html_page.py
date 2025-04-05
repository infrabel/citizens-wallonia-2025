from datetime import datetime

from airflow import DAG, Dataset
from airflow.models import TaskInstance
from airflow.operators.python import PythonOperator
from airflow.providers.common.sql.operators.sql import SQLExecuteQueryOperator
from jinja2 import Template, Environment, FileSystemLoader

with DAG(
    dag_id="publish_punctuality_page",
    start_date=datetime(2025, 1, 1),
    schedule=Dataset("infrabel.calculated_delay"),
    default_args={'owner': 'Joffrey', 'retries': 2},
    tags=['Gold', 'Punctuality'],
) as dag:

    load_delay_data = SQLExecuteQueryOperator(
        task_id='load_delay_data',
        sql="""
            SELECT month_name,
                   ROUND(mean_delay_minutes::numeric, 1) AS mean_delay_minutes,
                   on_time,
                   in_late
            FROM infrabel.calculated_delay
            WHERE year = 2024;
        """,
        conn_id='postgres:datawarehouse',
        show_return_value_in_logs=True,
    )

    def format_for_web(ti: TaskInstance):
        data = ti.xcom_pull("load_delay_data")

        return {
            "month_name": [row[0] for row in data],
            "mean_delay_minutes": [float(row[1]) for row in data],
            "on_time": [row[2] for row in data],
            "in_late": [row[3] for row in data]
        }

    format_data_for_web = PythonOperator(
        task_id='format_data_for_web',
        python_callable=format_for_web,
        show_return_value_in_logs=True,
    )

    def render_html(ti: TaskInstance):
        data = ti.xcom_pull(task_ids='format_data_for_web')
        # template = Template("""
        # <html>
        #     <head><title>Hello</title></head>
        #     <body>
        #         <h1>{{ month_name }}</h1>
        #     </body>
        # </html>
        # """)
        env = Environment(loader=FileSystemLoader('/usr/local/airflow/dags/'))
        template = env.get_template('page_template.html')

        html_content = template.render(data)
        with open("/usr/local/airflow/dags/page_output.html", "w") as f:
            f.write(html_content)

    render_page = PythonOperator(
        task_id="render_page",
        python_callable=render_html,
        provide_context=True,
        dag=dag,
    )

    load_delay_data >> format_data_for_web >> render_page
