"""Example usage of deploy function"""

from datetime import timedelta
from os import environ

from prefect import flow
from prefect.artifacts import create_table_artifact

from osw.utils.workflow import DeployConfig, DeployParam, deploy, tags_str_to_list

# Set environment variables
environ["PREFECT_DEPLOYMENT_NAME"] = "osw-python-deploy-example"
environ["PREFECT_DEPLOYMENT_DESCRIPTION"] = "Deployment of notify_teams.py"
environ["PREFECT_DEPLOYMENT_VERSION"] = "0.0.1"
environ["PREFECT_DEPLOYMENT_TAGS"] = "osw-python,example-deploy-flow"
environ["PREFECT_DEPLOYMENT_INTERVAL_MIN"] = "1"
# environ["PREFECT_DEPLOYMENT_CRON"] = "* * * * *"


@flow(log_prints=True)
def example_flow_to_deploy():
    """Example flow to be deployed"""
    print(f"Execution of example: {example_flow_to_deploy.__name__}!")
    # set example table artifact
    create_table_artifact(
        key="example-table",
        table=[
            {"name": "Alice", "age": 24},
            {"name": "Bob", "age": 25},
        ],
        description="Example table artifact",
    )


if __name__ == "__main__":
    """Deploy the example flow"""
    # Example using environment variables
    deploy(
        DeployParam(
            deployments=[
                DeployConfig(
                    flow=example_flow_to_deploy,
                    name=environ.get("PREFECT_DEPLOYMENT_NAME"),
                    description=environ.get("PREFECT_DEPLOYMENT_DESCRIPTION"),
                    version=environ.get("PREFECT_DEPLOYMENT_VERSION"),
                    tags=tags_str_to_list(environ.get("PREFECT_DEPLOYMENT_TAGS")),
                    interval=timedelta(
                        minutes=int(environ.get("PREFECT_DEPLOYMENT_INTERVAL_MIN"))
                    ),  # either interval or cron
                    # cron=environ.get("PREFECT_DEPLOYMENT_CRON"),
                )
            ],
            # remove_existing_deployments=True,
        )
    )

    # Clear secret environment variables
    del environ["PREFECT_DEPLOYMENT_NAME"]
    del environ["PREFECT_DEPLOYMENT_DESCRIPTION"]
    del environ["PREFECT_DEPLOYMENT_VERSION"]
    del environ["PREFECT_DEPLOYMENT_TAGS"]
    del environ["PREFECT_DEPLOYMENT_INTERVAL_MIN"]
    # del environ["PREFECT_DEPLOYMENT_CRON"]
