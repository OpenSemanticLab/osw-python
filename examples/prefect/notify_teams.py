"""Example of sending notifications to MS Teams on prefect flow failures"""

from os import environ

from prefect import flow
from pydantic import SecretStr

from osw.utils.workflow import NotifyTeams, NotifyTeamsParam

# Prerequisite: Set environment variable TEAMS_WEBHOOK_URL
# in CLI: export TEAMS_WEBHOOK_URL="https://prod..."
# in python uncomment below, DO NOT PUSH SECRETS TO GIT

# environ["TEAMS_WEBHOOK_URL"] = "https://prod..."


# Decorator must be configured with on_failure argument
@flow(
    # Microsoft Teams notification on failure ->
    # on_failure use `notify_teams` function without brackets as list element
    on_failure=[
        NotifyTeams(
            NotifyTeamsParam(
                teams_webhook_url=SecretStr(environ.get("TEAMS_WEBHOOK_URL")),
                # OPTIONAL, will be empty if no deploment is assigned
                deployment_name="osw-python-notify-teams-example",
            )
        ).notify_teams
    ],
    log_prints=True,
)
def example_error_flow():
    """Test flow that always fails"""

    raise ValueError(
        "oops! LOREM IPSUM DOLOR SIT AMET CONSECTETUR ADIPISICING ELIT " * 1
    )


if __name__ == "__main__":
    example_error_flow()
    # Clear secret environment variable
    del environ["TEAMS_WEBHOOK_URL"]
