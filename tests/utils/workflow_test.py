"""Test workflows for `osw-python` package"""

from os import environ
from unittest.mock import MagicMock
from uuid import uuid4

import httpx
import pytest
from prefect import flow, get_client
from prefect.testing.utilities import prefect_test_harness
from pydantic import SecretStr

from osw.core import OSW
from osw.utils.workflow import (
    DeployConfig,
    DeployParam,
    NotifyTeams,
    NotifyTeamsParam,
    _deploy,
    deploy,
    tags_str_to_list,
)


# ------------------------------ NOTIFICATIONS ---------------------
@flow(
    # Microsoft Teams notification on completion for testing
    # Notification only if env var
    on_completion=[
        NotifyTeams(
            NotifyTeamsParam(
                teams_webhook_url=SecretStr(environ.get("TEAMS_WEBHOOK_URL")),
                # OPTIONAL, will be empty if no deploment is assigned
                deployment_name="osw-python-notify-teams-test",
            )
        ).notify_teams
    ],
    log_prints=True,
)
def osw_python_teams_notify_test_flow():
    """Notify Microsoft Teams channel using a webhook"""
    return 42


def test_notify_teams():
    """Test of flow to notify Microsoft Teams channel using a webhook"""
    with prefect_test_harness():
        test_flow_run = osw_python_teams_notify_test_flow()
        assert test_flow_run == 42


# ------------------------------- DEPLOYMENTS -------------------------------
def test_tags_str_to_list(tags="osw-python,example-deploy-flow"):
    """Test of conversion of tags string to list"""
    assert tags_str_to_list("osw-python,example-deploy-flow") == [
        "osw-python",
        "example-deploy-flow",
    ]


@flow
def osw_python_test_flow_to_deploy():
    """Example flow to be deployed"""
    print(f"Execution of example: {osw_python_test_flow_to_deploy.__name__}!")


def make_deploy_param(**overrides) -> DeployParam:
    """Build a fresh DeployParam for a test.

    `_deploy` mutates `DeployConfig.name` in place, so a shared module level
    instance would leak state between tests. Every test gets its own object,
    optionally overriding any DeployParam field.
    """
    defaults = dict(
        deployments=[
            DeployConfig(
                flow=osw_python_test_flow_to_deploy,
                name="osw-python-deployment-test",
                description="Deployment of osw-python test flow",
                version="0.0.1",
                tags=["osw-python", "example-deploy-flow"],
            )
        ],
    )
    defaults.update(overrides)
    return DeployParam(**defaults)


@pytest.mark.asyncio
async def test_deploy_serve(monkeypatch):
    """Test that _deploy applies the deployment and hands it to serve"""
    served = []

    async def fake_serve(*deployments):
        served.append(deployments)

    monkeypatch.setattr("osw.utils.workflow.serve", fake_serve)
    # public_url is None, so _deploy falls back to the ambient env var; keep
    # it unset here so a leftover value on the machine cannot make the
    # ApiGateway shim's cleanup pop a var this test never set.
    monkeypatch.delenv("PREFECT_API_URL", raising=False)

    param = make_deploy_param()

    with prefect_test_harness():
        await _deploy(param=param)

        assert len(served) == 1
        assert len(served[0]) == 1

        # Read the deployment back from the Prefect API to prove
        # config.apply() really registered it, not just constructed it.
        async with get_client() as client:
            deployment = await client.read_deployment_by_name(
                f"{osw_python_test_flow_to_deploy.name}/osw-python-deployment-test"
            )

        assert deployment.name == "osw-python-deployment-test"
        assert deployment.description == "Deployment of osw-python test flow"
        assert deployment.version == "0.0.1"
        assert deployment.tags == ["osw-python", "example-deploy-flow"]


@pytest.mark.asyncio
async def test_deploy_defaults_deployment_name(monkeypatch):
    """Test that _deploy defaults the deployment name from the flow name"""

    async def fake_serve(*deployments):
        pass

    monkeypatch.setattr("osw.utils.workflow.serve", fake_serve)
    # See test_deploy_serve: public_url is None here too, so isolate the
    # ambient PREFECT_API_URL from this test.
    monkeypatch.delenv("PREFECT_API_URL", raising=False)

    param = make_deploy_param(
        deployments=[DeployConfig(flow=osw_python_test_flow_to_deploy, name=None)]
    )

    with prefect_test_harness():
        await _deploy(param=param)

    assert (
        param.deployments[0].name == f"{osw_python_test_flow_to_deploy.name}-deployment"
    )


def test_deploy_sync_wrapper(monkeypatch):
    """Test that deploy() runs _deploy to completion via the sync wrapper

    Not async: deploy() calls asyncio.run/asyncio.Runner internally, which
    require that no event loop is already running.
    """
    served = []

    async def fake_serve(*deployments):
        served.append(deployments)

    monkeypatch.setattr("osw.utils.workflow.serve", fake_serve)
    # See test_deploy_serve: public_url is None here too, so isolate the
    # ambient PREFECT_API_URL from this test.
    monkeypatch.delenv("PREFECT_API_URL", raising=False)

    param = make_deploy_param()

    with prefect_test_harness():
        deploy(param=param)

    assert len(served) == 1


@pytest.mark.asyncio
async def test_deploy_registers_flow_with_osw(monkeypatch):
    """Test that _deploy registers each deployed flow via register_flow"""
    calls = []

    async def fake_serve(*deployments):
        pass

    async def fake_register_flow(osw_instance, flow, namespace_uuid, public_url):
        calls.append({
            "flow": flow,
            "namespace_uuid": namespace_uuid,
            "public_url": public_url,
        })

    monkeypatch.setattr("osw.utils.workflow.serve", fake_serve)
    monkeypatch.setattr("osw.utils.workflow.register_flow", fake_register_flow)

    namespace_uuid = uuid4()
    param = make_deploy_param(
        osw=MagicMock(spec=OSW),
        namespace_uuid=namespace_uuid,
        # Non-gateway URL: the ApiGateway shim must not trigger here.
        public_url="https://example.com/w/api.php",
    )

    with prefect_test_harness():
        await _deploy(param=param)

    assert len(calls) == 1
    assert calls[0]["flow"] is osw_python_test_flow_to_deploy
    assert calls[0]["namespace_uuid"] == namespace_uuid
    assert calls[0]["public_url"] == "https://example.com/w/api.php"


@pytest.mark.asyncio
async def test_deploy_apigateway_shim_restores_httpx(monkeypatch, tmp_path):
    """Test that the ApiGateway shim patches httpx and later restores it

    Guards against the global httpx.AsyncClient patch leaking into the rest
    of the test session. The positive assertion inside fake_serve proves the
    shim actually ran; without it, a vacuous shim (never triggered) would
    also make the restore assertions trivially true.
    """

    async def fake_serve(*deployments):
        # Proof the patch was applied, not just that it is restored later.
        assert httpx.AsyncClient.__init__ is not original_httpx_init

    async def fake_register_flow(**kwargs):
        pass

    install_calls = []

    def fake_install_gateway_hook():
        install_calls.append(True)

    monkeypatch.setattr("osw.utils.workflow.serve", fake_serve)
    monkeypatch.setattr("osw.utils.workflow.register_flow", fake_register_flow)
    monkeypatch.setattr(
        "osw.utils.workflow.install_gateway_hook", fake_install_gateway_hook
    )
    # Force the "hook not yet installed" branch deterministically. Without
    # this, _get_site_packages() reads the real venv, and on a machine that
    # already installed the real .pth file (exactly what this feature does
    # in production), install_gateway_hook would be skipped and this test
    # would fail.
    monkeypatch.setattr("osw.utils.workflow._get_site_packages", lambda: str(tmp_path))
    monkeypatch.delenv("PREFECT_API_URL", raising=False)

    # pydantic v1 shallow copies BaseModel-typed fields on validation, so
    # the object that reaches _deploy as param.osw is a copy of this mock,
    # not this instance. Only its recognized type matters for the shim to
    # trigger, so no further attributes need to be configured here.
    fake_osw = MagicMock(spec=OSW)

    param = make_deploy_param(
        osw=fake_osw,
        public_url="https://example.com/w/rest.php/apigateway/",
    )

    original_httpx_init = httpx.AsyncClient.__init__

    try:
        with prefect_test_harness():
            await _deploy(param=param)
    finally:
        # Defensive restore for this test itself: if an assertion above
        # fails mid-test, this still prevents the patch from leaking into
        # the rest of the session.
        if httpx.AsyncClient.__init__ is not original_httpx_init:
            httpx.AsyncClient.__init__ = original_httpx_init

    assert httpx.AsyncClient.__init__ is original_httpx_init
    assert "PREFECT_API_URL" not in environ
    assert install_calls == [True]


@pytest.mark.asyncio
async def test_deploy_preserves_ambient_prefect_api_url(monkeypatch):
    """Test that _deploy does not remove an ambient PREFECT_API_URL it never set

    Reproduces a bug where the cleanup popped PREFECT_API_URL based on the
    URL shape alone, even when the ApiGateway shim body never ran (because
    osw is None), deleting a variable _deploy never set in the first place.
    """

    async def fake_serve(*deployments):
        pass

    monkeypatch.setattr("osw.utils.workflow.serve", fake_serve)

    gateway_url = "https://example.com/w/rest.php/apigateway/"
    monkeypatch.setenv("PREFECT_API_URL", gateway_url)

    # osw=None and public_url=None: gateway_url falls back to the ambient
    # env var, but the shim is skipped because param.osw is None.
    param = make_deploy_param(osw=None, public_url=None)

    with prefect_test_harness():
        await _deploy(param=param)

    assert environ["PREFECT_API_URL"] == gateway_url


@pytest.mark.asyncio
async def test_deploy_restores_httpx_when_gateway_hook_fails(monkeypatch, tmp_path):
    """Test that a failure while installing the gateway hook does not leak httpx

    Reproduces a bug where the global mutations (PREFECT_API_URL override,
    httpx.AsyncClient.__init__ patch) happen before the try/finally starts,
    so a failure in the ApiGateway shim setup itself (e.g. install_gateway_hook
    hitting a read-only site-packages) left both globals patched for the rest
    of the process.
    """

    async def fake_serve(*deployments):
        pass

    async def fake_register_flow(**kwargs):
        pass

    def fake_install_gateway_hook():
        # The httpx patch (:702) precedes the hook install (:707), so it
        # must already be live here.
        assert httpx.AsyncClient.__init__ is not original_httpx_init
        raise PermissionError("no write access to site-packages")

    monkeypatch.setattr("osw.utils.workflow.serve", fake_serve)
    monkeypatch.setattr("osw.utils.workflow.register_flow", fake_register_flow)
    monkeypatch.setattr(
        "osw.utils.workflow.install_gateway_hook", fake_install_gateway_hook
    )
    monkeypatch.setattr("osw.utils.workflow._get_site_packages", lambda: str(tmp_path))

    original_api_url = environ.get("PREFECT_API_URL")
    original_httpx_init = httpx.AsyncClient.__init__

    fake_osw = MagicMock(spec=OSW)
    param = make_deploy_param(
        osw=fake_osw,
        public_url="https://example.com/w/rest.php/apigateway/",
    )

    try:
        with prefect_test_harness():
            with pytest.raises(PermissionError):
                await _deploy(param=param)

        assert httpx.AsyncClient.__init__ is original_httpx_init
        assert environ.get("PREFECT_API_URL") == original_api_url
    finally:
        # Force-restore regardless of the assertions above, so that while
        # this test is RED it does not poison the rest of the session.
        if httpx.AsyncClient.__init__ is not original_httpx_init:
            httpx.AsyncClient.__init__ = original_httpx_init
        if original_api_url is not None:
            environ["PREFECT_API_URL"] = original_api_url
        else:
            environ.pop("PREFECT_API_URL", None)


@pytest.mark.asyncio
async def test_deploy_restores_previous_prefect_api_url(monkeypatch, tmp_path):
    """Test that _deploy restores a real ambient PREFECT_API_URL, not just pops it

    Pins the "restore the caller's value" branch of the Bug A fix
    (`if _original_api_url is not None: ...`), which was otherwise never
    exercised: no other test both triggers the shim AND has a known
    non-empty ambient PREFECT_API_URL to be restored afterwards.
    """

    async def fake_serve(*deployments):
        pass

    async def fake_register_flow(**kwargs):
        pass

    install_calls = []

    def fake_install_gateway_hook():
        install_calls.append(True)

    monkeypatch.setattr("osw.utils.workflow.serve", fake_serve)
    monkeypatch.setattr("osw.utils.workflow.register_flow", fake_register_flow)
    monkeypatch.setattr(
        "osw.utils.workflow.install_gateway_hook", fake_install_gateway_hook
    )
    monkeypatch.setattr("osw.utils.workflow._get_site_packages", lambda: str(tmp_path))

    # Deliberately not a gateway URL: this is the ambient value that should
    # be restored, distinct from the gateway public_url used to trigger the
    # shim below.
    monkeypatch.setenv("PREFECT_API_URL", "http://ambient.example/api")

    fake_osw = MagicMock(spec=OSW)
    param = make_deploy_param(
        osw=fake_osw,
        public_url="https://example.com/w/rest.php/apigateway/",
    )

    with prefect_test_harness():
        await _deploy(param=param)

    assert environ["PREFECT_API_URL"] == "http://ambient.example/api"
    assert install_calls == [True]


@pytest.mark.asyncio
async def test_deploy_restores_httpx_when_deployment_fails(monkeypatch, tmp_path):
    """Test that the httpx patch does not leak when the deployment loop raises

    Reproduces a bug where `try/finally` only wrapped `await serve(...)`, so
    a failure earlier in the deployment loop (here, register_flow raising)
    left httpx.AsyncClient.__init__ globally patched for the rest of the
    process, and PREFECT_API_URL overridden, because cleanup never ran.
    """

    async def fake_serve(*deployments):
        pass

    async def fake_register_flow(**kwargs):
        # Proof the patch was applied before this test relies on it leaking.
        assert httpx.AsyncClient.__init__ is not original_httpx_init
        raise RuntimeError("boom")

    monkeypatch.setattr("osw.utils.workflow.serve", fake_serve)
    monkeypatch.setattr("osw.utils.workflow.register_flow", fake_register_flow)
    # See test_deploy_apigateway_shim_restores_httpx for why this is forced.
    monkeypatch.setattr("osw.utils.workflow._get_site_packages", lambda: str(tmp_path))

    original_api_url = environ.get("PREFECT_API_URL")
    original_httpx_init = httpx.AsyncClient.__init__

    fake_osw = MagicMock(spec=OSW)
    param = make_deploy_param(
        osw=fake_osw,
        public_url="https://example.com/w/rest.php/apigateway/",
    )

    try:
        with prefect_test_harness():
            with pytest.raises(RuntimeError, match="boom"):
                await _deploy(param=param)

        assert httpx.AsyncClient.__init__ is original_httpx_init
        assert environ.get("PREFECT_API_URL") == original_api_url
    finally:
        # Force-restore regardless of the assertions above, so that while
        # this test is RED it does not poison the rest of the session.
        if httpx.AsyncClient.__init__ is not original_httpx_init:
            httpx.AsyncClient.__init__ = original_httpx_init
        if original_api_url is not None:
            environ["PREFECT_API_URL"] = original_api_url
        else:
            environ.pop("PREFECT_API_URL", None)
