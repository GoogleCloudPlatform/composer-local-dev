from airflow import DAG
from airflow.operators.python_operator import PythonOperator
from datetime import datetime

def hello_world():
    print("Hello World")

default_args = {
    'start_date': datetime(2024, 1, 1),
}

with DAG(
    dag_id='hello_world_dag',
    default_args=default_args,
    schedule_interval='@once',
    catchup=False,
    tags=['example'],
) as dag:

    task_hello = PythonOperator(
        task_id='print_hello',
        python_callable=hello_world,
    )
