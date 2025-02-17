"""Prefect utils as support for OpenSemanticWorld."""

from prefect.blocks.notifications import MicrosoftTeamsWebhook
from prefect.client.schemas.objects import FlowRun
from prefect.settings import PREFECT_API_URL
from prefect.states import State
from pydantic import BaseModel, SecretStr


class NotifyTeamsParam(BaseModel):
    """Parameter set for notifying Microsoft Teams using class NotifyTeams"""

    deployment_name: str
    teams_webhook_url: SecretStr


class NotifyTeams(NotifyTeamsParam):
    """Notify Microsoft Teams channel using a webhook"""

    def __init__(self, notify_teams_param: NotifyTeamsParam):
        super().__init__(**notify_teams_param.model_dump())

    def notify_teams(
        self,
        flow,
        flow_run: FlowRun,
        state: State,
    ):

        host_url = str(PREFECT_API_URL.value()).replace("/api", "")

        if flow_run.deployment_id is not None:
            deployment_url = (
                f"{host_url}/deployments/deployment/{flow_run.deployment_id}"
            )
        else:
            deployment_url = ""
        _flow_run = f"**🚨Flow Run: [{flow.name} > {flow_run.name}]({host_url}/flow-runs/flow-run/{flow_run.id}) ❗{state.name}❗**\n\n"  # noqa
        if self.deployment_name == "" or self.deployment_name is None:
            _deployment = f"🚀 Deployment: _[{flow_run.deployment_id}]({deployment_url})_\n\n"  # noqa
        else:
            _deployment = f"🚀 Deployment: _[{self.deployment_name}]({deployment_url})_\n\n"  # noqa
        _ts = f"🕑 Timestamp: _{flow_run.state.timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')}_\n\n"  # noqa
        if flow_run.tags != []:
            _tags = f"🏷️ Tags: _#{' #'.join(flow_run.tags)}_\n\n"
        else:
            _tags = ""

        _message = f"📜 Message:\n\n_`{state.message}`_"

        MicrosoftTeamsWebhook(url=self.teams_webhook_url.get_secret_value()).notify(
            body=(_flow_run + _deployment + _ts + _tags + _message)
        )
