"""
Example Airflow DAG that uses Google PubSub services.
"""
import os

from airflow import models
from airflow.operators.bash_operator import BashOperator
from airflow.providers.google.cloud.operators.pubsub import (
    PubSubCreateSubscriptionOperator,
    PubSubCreateTopicOperator,
    PubSubDeleteSubscriptionOperator,
    PubSubDeleteTopicOperator,
    PubSubPublishMessageOperator,
    PubSubPullOperator,
)
from airflow.providers.google.cloud.sensors.pubsub import PubSubPullSensor
from airflow.utils.dates import days_ago

GCP_PROJECT_ID = os.environ.get("GCP_PROJECT_ID", "your-project-id")
TOPIC_FOR_SENSOR_DAG = "PubSubSensorTestTopic"
TOPIC_FOR_OPERATOR_DAG = "PubSubOperatorTestTopic"
MESSAGE = {"data": b"Tool", "attributes": {"name": "wrench", "mass": "1.3kg", "count": "3"}}

echo_cmd = """
{% for m in task_instance.xcom_pull('pull_messages') %}
    echo "AckID: {{ m.get('ackId') }}, Base64-Encoded: {{ m.get('message') }}"
{% endfor %}
"""

with models.DAG(
    "example_gcp_pubsub_sensor",
    schedule_interval=None,
    start_date=days_ago(1),
) as example_sensor_dag:
    create_topic = PubSubCreateTopicOperator(
        task_id="create_topic", topic=TOPIC_FOR_SENSOR_DAG, project_id=GCP_PROJECT_ID, fail_if_exists=False
    )

    subscribe_task = PubSubCreateSubscriptionOperator(
        task_id="subscribe_task", project_id=GCP_PROJECT_ID, topic=TOPIC_FOR_SENSOR_DAG
    )

    subscription = "{{ task_instance.xcom_pull('subscribe_task') }}"

    pull_messages = PubSubPullSensor(
        task_id="pull_messages",
        ack_messages=True,
        project_id=GCP_PROJECT_ID,
        subscription=subscription,
    )

    pull_messages_result = BashOperator(task_id="pull_messages_result", bash_command=echo_cmd)

    publish_task = PubSubPublishMessageOperator(
        task_id="publish_task",
        project_id=GCP_PROJECT_ID,
        topic=TOPIC_FOR_SENSOR_DAG,
        messages=[MESSAGE] * 10,
    )

    unsubscribe_task = PubSubDeleteSubscriptionOperator(
        task_id="unsubscribe_task",
        project_id=GCP_PROJECT_ID,
        subscription="{{ task_instance.xcom_pull('subscribe_task') }}",
    )

    delete_topic = PubSubDeleteTopicOperator(
        task_id="delete_topic", topic=TOPIC_FOR_SENSOR_DAG, project_id=GCP_PROJECT_ID
    )

    create_topic >> subscribe_task >> [publish_task, pull_messages]
    pull_messages >> pull_messages_result >> unsubscribe_task >> delete_topic