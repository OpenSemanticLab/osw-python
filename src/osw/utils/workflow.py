"""Prefect utils as support for OpenSemanticWorld."""

import asyncio
import os
import re
import sys
import uuid as uuid_module
from datetime import timedelta
from inspect import signature
from os import environ
from typing import Any, Dict, Iterable, List, Optional, Union
from uuid import UUID

import httpx
from prefect import Flow, get_client, serve
from prefect.blocks.notifications import MicrosoftTeamsWebhook
from prefect.blocks.system import Secret
from prefect.client.schemas.objects import FlowRun
from prefect.settings import PREFECT_API_URL
from prefect.states import State
from pydantic import SecretStr
from pydantic.v1 import BaseModel

import osw.model.entity as model
from osw.auth import CredentialManager
from osw.core import OSW
from osw.utils._httpx_gateway import _install as _install_gateway_hook
from osw.utils.wiki import get_full_title
from osw.wtsite import WtSite

# Auto-patch httpx at import time if PREFECT_API_URL is an ApiGateway URL.
# This ensures the transport is active for ALL Prefect API calls, not just
# those inside deploy(). The patch is lazy — no MW login until first request.
_install_gateway_hook()


# ------------------------------ CONNECTION ---------------------
class ConnectionSettings(BaseModel):
    """Connection data for OSW.

    If osw_user_name or osw_domain are not provided, they are read from
    environment variables OSW_USER and OSW_SERVER respectively.
    """

    osw_user_name: Optional[str] = None
    """The login username. Falls back to env var OSW_USER."""
    osw_domain: Optional[str] = None
    """The domain of the instance. Falls back to env var OSW_SERVER."""


def connect(settings: Optional[ConnectionSettings] = None) -> OSW:
    """Connect to an OSW instance.

    Reads OSW_USER, OSW_SERVER, OSW_PASSWORD from environment variables.
    If OSW_PASSWORD is not set, falls back to a Prefect Secret named
    ``<username>-<domain-with-dashes>`` (e.g. ``mybot-wiki-dev-open-semantic-lab-org``).

    Parameters
    ----------
    settings
        Optional connection settings. If None, all values come from env vars.

    Returns
    -------
    OSW
        A connected OSW instance.
    """
    if settings is None:
        settings = ConnectionSettings()
    if environ.get("OSW_USER"):
        settings.osw_user_name = environ["OSW_USER"]
    if environ.get("OSW_SERVER"):
        settings.osw_domain = environ["OSW_SERVER"]
    password = environ.get("OSW_PASSWORD", "")
    if not password:
        # fetch secret stored in prefect server from calculated name
        password = Secret.load(
            settings.osw_user_name.lower() + "-" + settings.osw_domain.replace(".", "-")
        ).get()
    cm = CredentialManager()
    cm.add_credential(
        CredentialManager.UserPwdCredential(
            iri=settings.osw_domain,
            username=settings.osw_user_name,
            password=password,
        )
    )
    wtsite = WtSite(WtSite.WtSiteConfig(iri=settings.osw_domain, cred_mngr=cm))
    return OSW(site=wtsite)


# ------------------------------ REQUESTS ---------------------
class WorkflowRequest(BaseModel):
    """Base request model for OSW Prefect workflows.

    Provides common fields for provenance tracking and targeting.
    Extend this class with workflow-specific fields.
    """

    uuid: UUID = None
    """UUIDv4 of the request (for provenance tracking)."""
    osw_domain: Optional[str] = None
    """The domain of the OSW instance. Falls back to env var OSW_SERVER."""
    subject: Optional[str] = None
    """The target page title to associate results with."""

    class Config:
        arbitrary_types_allowed = True


# ------------------------------ API GATEWAY ---------------------
class ApiGatewayTransport(httpx.AsyncBaseTransport):
    """httpx transport that routes Prefect API calls through MW ApiGateway.

    Rewrites URLs from Prefect format to ApiGateway ``?path=`` format
    and injects MediaWiki session cookies + CSRF tokens.
    """

    def __init__(self, gateway_url: str, mw_site, csrf_required: bool = True):
        """
        Parameters
        ----------
        gateway_url
            ApiGateway endpoint URL, e.g.
            ``https://osw.example.com/w/rest.php/apigateway/v1/prefect``
        mw_site
            Authenticated mwclient Site instance.
        csrf_required
            Whether to send MW CSRF token for write methods.
        """
        self._gateway_url = gateway_url.rstrip("/")
        self._mw_site = mw_site
        self._csrf_token = None
        self._csrf_required = csrf_required

    def _get_csrf_token(self) -> str:
        if self._csrf_token is None:
            self._csrf_token = self._mw_site.get_token("csrf")
        return self._csrf_token

    def _get_cookies(self) -> dict:
        return dict(self._mw_site.connection.cookies)

    def _rewrite_request(self, request: httpx.Request) -> httpx.Request:
        from urllib.parse import quote, urlparse

        parsed = urlparse(str(request.url))
        gateway_parsed = urlparse(self._gateway_url)

        # Extract subpath: everything after the gateway path prefix
        # preserve trailing slash (Prefect/FastAPI requires it)
        subpath = parsed.path[len(gateway_parsed.path) :].lstrip("/")

        # Build query: path=<subpath>
        # Original query params go into ApiGateway's "query" parameter
        # (ApiGateway only forwards path, query, token, headers to backend)
        query_parts = [f"path={quote(subpath, safe='/')}"]
        if parsed.query:
            query_parts.append(f"query={quote(parsed.query, safe='')}")

        method = request.method.upper()
        if method in ("POST", "PUT", "PATCH", "DELETE") and self._csrf_required:
            query_parts.append(f"token={quote(self._get_csrf_token(), safe='')}")

        new_url = f"{self._gateway_url}?{'&'.join(query_parts)}"

        headers = dict(request.headers)
        cookies = self._get_cookies()
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        if cookie_str:
            headers["cookie"] = cookie_str
        # MW REST API requires Origin + CSRF token for POST requests
        origin = f"{gateway_parsed.scheme}://{gateway_parsed.netloc}"
        headers["origin"] = origin
        if method in ("POST", "PUT", "PATCH", "DELETE"):
            headers["x-csrf-token"] = self._get_csrf_token()

        return httpx.Request(
            method=method,
            url=new_url,
            headers=headers,
            content=request.content,
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        import logging

        log = logging.getLogger(__name__)
        log.debug("ApiGateway: %s %s", request.method, request.url)
        rewritten = self._rewrite_request(request)
        log.debug("ApiGateway rewritten: %s %s", rewritten.method, rewritten.url)
        # Create a fresh transport per request to avoid event-loop binding
        inner = httpx.AsyncHTTPTransport()
        response = await inner.handle_async_request(rewritten)
        log.debug("ApiGateway response: %s", response.status_code)
        # Follow redirects by rewriting internal Location URLs back
        # through the gateway (backend may return internal Docker URLs)
        if response.status_code in (301, 302, 307, 308):
            location = response.headers.get("location")
            if location:
                from urllib.parse import quote
                from urllib.parse import urlparse as _urlparse

                loc_parsed = _urlparse(location)
                api_idx = loc_parsed.path.find("/api/")
                if api_idx >= 0:
                    redirect_subpath = loc_parsed.path[api_idx + 5 :]
                else:
                    redirect_subpath = loc_parsed.path.lstrip("/")
                redirect_subpath = redirect_subpath.lstrip("/")
                redirect_query = [f"path={redirect_subpath}"]
                if loc_parsed.query:
                    redirect_query.append(f"query={quote(loc_parsed.query, safe='')}")
                redirect_url = f"{self._gateway_url}?{'&'.join(redirect_query)}"
                log.debug("ApiGateway following redirect: %s", redirect_url)
                redirect_req = httpx.Request(
                    method=(
                        rewritten.method
                        if response.status_code in (307, 308)
                        else "GET"
                    ),
                    url=redirect_url,
                    headers=rewritten.headers,
                    content=(
                        rewritten.content
                        if response.status_code in (307, 308)
                        else None
                    ),
                )
                response = await httpx.AsyncHTTPTransport().handle_async_request(
                    redirect_req
                )
        # Refresh CSRF token and retry once on 403
        if response.status_code == 403:
            self._csrf_token = None
            rewritten = self._rewrite_request(request)
            response = await httpx.AsyncHTTPTransport().handle_async_request(rewritten)
        return response


def get_gateway_httpx_settings(gateway_url: str, osw_instance: OSW) -> dict:
    """Create httpx_settings for routing Prefect SDK through ApiGateway.

    Returns a dict suitable for ``get_client(httpx_settings=...)``.

    Parameters
    ----------
    gateway_url
        ApiGateway endpoint URL.
    osw_instance
        A connected OSW instance (provides mwclient session).
    """
    transport = ApiGatewayTransport(
        gateway_url=gateway_url,
        mw_site=osw_instance.site.mw_site,
        csrf_required=False,
    )
    return {"transport": transport, "base_url": gateway_url}


def _is_apigateway_url(url: str) -> bool:
    return "/rest.php/apigateway/" in url


_PTH_FILENAME = "osw-httpx-gateway.pth"
_PTH_MODULE = "_osw_httpx_gateway.py"
_PTH_CONTENT = "import _osw_httpx_gateway\n"


def _get_site_packages() -> str:
    """Return the Lib/site-packages directory (not the venv root)."""
    import site

    for sp in site.getsitepackages():
        if sp.endswith("site-packages"):
            return sp
    return site.getsitepackages()[-1]


def install_gateway_hook():
    """Install the .pth startup hook into site-packages.

    Copies ``_httpx_gateway.py`` as a standalone module (no ``osw.`` prefix)
    so it's importable before editable installs are on ``sys.path``.
    """
    import shutil

    sp = _get_site_packages()
    src = os.path.join(os.path.dirname(__file__), "_httpx_gateway.py")
    shutil.copy2(src, os.path.join(sp, _PTH_MODULE))
    with open(os.path.join(sp, _PTH_FILENAME), "w") as f:
        f.write(_PTH_CONTENT)
    print(f"Installed gateway hook in {sp}")


def uninstall_gateway_hook():
    """Remove the .pth startup hook and module from site-packages."""
    sp = _get_site_packages()
    for name in (_PTH_FILENAME, _PTH_MODULE):
        target = os.path.join(sp, name)
        if os.path.exists(target):
            os.remove(target)
            print(f"Removed {target}")


# ------------------------------ NOTIFICATIONS ---------------------
class NotifyTeamsParam(BaseModel):
    """Parameter set for notifying Microsoft Teams using class NotifyTeams"""

    teams_webhook_url: SecretStr
    """Microsoft Teams webhook URL containing a secret"""
    deployment_name: Optional[str] = None
    """Deployment name to be displayed in the notification"""

    # allow arbitrary types for compatibility with pydantic v1
    class Config:
        arbitrary_types_allowed = True


class NotifyTeams(NotifyTeamsParam):
    """Notify Microsoft Teams channel using a webhook"""

    def __init__(self, notify_teams_param: NotifyTeamsParam):
        # super().__init__(**notify_teams_param.model_dump())  # pydantic v2
        super().__init__(**notify_teams_param.dict())  # pydantic v1

    def notify_teams(
        self,
        flow,
        flow_run: FlowRun,
        state: State,
    ):

        host_url = str(PREFECT_API_URL.value()).replace("/api", "")

        _flow_run = f"**🚨Flow Run: [{flow.name} > {flow_run.name}]({host_url}/flow-runs/flow-run/{flow_run.id}) ❗{state.name}❗**\n\n"  # noqa

        if flow_run.deployment_id is not None:
            # Assigned deployment found
            deployment_url = (
                f"{host_url}/deployments/deployment/{flow_run.deployment_id}"
            )
            if self.deployment_name == "" or self.deployment_name is None:
                _deployment = f"🚀 Deployment: _[{flow_run.deployment_id}]({deployment_url})_\n\n"  # noqa
            else:
                _deployment = f"🚀 Deployment: _[{self.deployment_name}]({deployment_url})_\n\n"  # noqa
        else:
            # No deployment assigned
            _deployment = "🚀 Deployment: _Just flow, no deployment_\n\n"

        _ts = f"🕑 Timestamp: _{flow_run.state.timestamp.strftime('%Y-%m-%d %H:%M:%S %Z')}_\n\n"  # noqa
        if flow_run.tags != []:
            _tags = f"🏷️ Tags: _#{' #'.join(flow_run.tags)}_\n\n"
        else:
            _tags = ""

        if state.message is None:
            _message = "No message provided."
        else:
            _message = f"📜 Message:\n\n_`{state.message}`_"

        MicrosoftTeamsWebhook(
            url=str(self.teams_webhook_url.get_secret_value())
        ).notify(body=(_flow_run + _deployment + _ts + _tags + _message))


# ------------------------------- DEPLOYMENTS -------------------------------
def tags_str_to_list(tags: str) -> List[str]:
    """Remove tags whitespaces, newlines, tabs, empty strings, split comma"""
    return list(filter(None, re.sub(r"\s+", "", tags).split(",")))


# def filter_arguments(func, args_dict):
#     """Filter arguments for a function based on its signature"""
#     sig = signature(func)
#     valid_params = sig.parameters
#     filtered_args = {k: v for k, v in args_dict.items() if k in valid_params}
#     return filtered_args


def match_func_model_args(func, model: BaseModel) -> dict:
    """Match function arguments with model attributes"""
    valid_params = set(signature(func).parameters)
    # model_attrs = model.model_dump().items() # pydantic v2
    model_attrs = model.dict().items()  # pydantic v1
    matched_args = {k: v for k, v in model_attrs if k in valid_params}
    return matched_args


class DeployConfig(BaseModel):
    """Prefect deployment configuration"""

    flow: Flow  # to be excluded in `flow.to_deployment()` function
    # Union instead of | for compatibility with pydantic v1, python < 3.10
    name: Union[str, None] = None
    description: Union[str, None] = None
    interval: Union[
        Iterable[Union[int, float, timedelta]], int, float, timedelta, None
    ] = None
    cron: Union[Iterable[str], str, None] = None
    version: Union[str, None] = None
    tags: Union[List[str], None] = None
    rrule: Union[Iterable[str], str, None] = None
    paused: Union[bool, None] = None
    is_schedule_active: Union[bool, None] = None
    parameters: Union[dict, None] = None
    enforce_parameter_schema: bool = False
    work_pool_name: Union[str, None] = None
    work_queue_name: Union[str, None] = None
    job_variables: Union[Dict[str, Any], None] = None
    deployment_id: Union[str, None] = None

    class Config:
        arbitrary_types_allowed = True


class DeployParam(BaseModel):
    """Parameter set for deploying flows as deployments"""

    deployments: List[DeployConfig]
    """List of deployments to be served"""
    # TODO: Implement remove_existing_deployments
    remove_existing_deployments: Optional[bool] = False
    """Will remove existing deployments of the specified flows/software"""
    osw: Optional[OSW] = None
    """If provided, deployed flows are registered as Software + PrefectFlow
    entities on the OSW instance."""
    namespace_uuid: Optional[UUID] = None
    """Static UUIDv5 namespace for stable Software entity UUIDs.
    If None, a default namespace is used."""
    public_url: Optional[str] = None
    """Public Prefect API URL stored in the PrefectFlow entity.
    Use this when the PREFECT_API_URL used by the worker differs from the
    URL clients (e.g. prefect.js) should use to reach the API.
    Example: PREFECT_API_URL='http://localhost:4200/api' but clients need
    'https://example.com/w/rest.php/apigateway'."""

    class Config:
        arbitrary_types_allowed = True


# Default UUIDv5 namespace for flow registration
_DEFAULT_NAMESPACE_UUID = uuid_module.UUID("0dd6c54a-b162-4552-bab9-9942ccaf4f41")


async def register_flow(
    osw_instance: OSW,
    flow: Flow,
    namespace_uuid: Optional[UUID] = None,
    public_url: Optional[str] = None,
) -> None:
    """Register a Prefect flow as Software + PrefectFlow entities on OSW.

    Creates or updates:
    - A Software entity with a stable UUID (uuid5 from flow name)
    - A PrefectFlow entity with the UUID from the Prefect API

    Parameters
    ----------
    osw_instance
        A connected OSW instance.
    flow
        The Prefect Flow object to register.
    namespace_uuid
        UUIDv5 namespace for generating the Software entity UUID.
        If None, uses a default namespace.
    public_url
        Public Prefect API URL to store in the PrefectFlow entity.
        If None, PREFECT_API_URL env var is used.
    """
    if namespace_uuid is None:
        namespace_uuid = _DEFAULT_NAMESPACE_UUID

    # ensure required schemas are loaded (needed if entity.py is regenerated)
    if not hasattr(model, "Software") or not hasattr(model, "PrefectFlow"):
        osw_instance.fetch_schema(
            OSW.FetchSchemaParam(
                schema_title=[
                    "Category:OSW77e749fc598341ac8b6d2fff21574058",  # Software
                    "Category:OSW72eae3c8f41f4a22a94dbc01974ed404",  # PrefectFlow
                ],
                mode="replace",
            )
        )

    # fetch flow uuid from Prefect API
    gateway_url = public_url or environ.get("PREFECT_API_URL", "")
    httpx_kw = {}
    if _is_apigateway_url(gateway_url):
        httpx_kw = get_gateway_httpx_settings(gateway_url, osw_instance)
    async with get_client(httpx_settings=httpx_kw or None) as client:
        response = await client.read_flow_by_name(flow.name)
        flow_uuid = response.id

    # create Software entity
    this_tool = model.Software(
        uuid=uuid_module.uuid5(namespace_uuid, flow.name),
        label=[model.Label(text=flow.name)],
        description=[model.Description(text=flow.description or "")],
    )

    # create PrefectFlow entity
    # use public_url if provided, otherwise fall back to PREFECT_API_URL
    from urllib.parse import urlparse

    entity_url = public_url or environ.get("PREFECT_API_URL", "")
    parsed = urlparse(entity_url)
    prefect_domain = parsed.hostname or ""
    prefect_schema = parsed.scheme or "https"
    prefect_port = [parsed.port] if parsed.port else None
    prefect_path = parsed.path or None
    # reconstruct full URL preserving query params and fragment
    prefect_url = (
        f"{prefect_schema}://{prefect_domain}"
        + (f":{parsed.port}" if parsed.port else "")
        + (prefect_path or "")
    )
    if parsed.query:
        prefect_url += f"?{parsed.query}"
    if parsed.fragment:
        prefect_url += f"#{parsed.fragment}"
    this_flow = model.PrefectFlow(
        uuid=flow_uuid,
        label=[model.Label(text=flow.name + " Prefect Flow")],
        description=[model.Description(text=flow.description or "")],
        flow_id=str(flow_uuid),
        hosted_software=[get_full_title(this_tool)],
        domain=prefect_domain,
        schema_=prefect_schema,
        network_port=prefect_port,
        url_path=prefect_path,
        url=prefect_url,
    )

    # delete stale PrefectFlow entities that reference the same Software
    # (avoids confusing the prefect.js reverse lookup)
    software_title = get_full_title(this_tool)
    stale_titles = osw_instance.site.semantic_search(f"[[Hosts::{software_title}]]")
    new_flow_title = "Item:" + OSW.get_osw_id(flow_uuid)
    stale_entities = []
    for title in stale_titles:
        if title != new_flow_title:
            entity = osw_instance.load_entity(title)
            if entity is not None:
                stale_entities.append(entity)
    if stale_entities:
        for e in stale_entities:
            print(
                f"WARNING: Deleting stale PrefectFlow entity "
                f"'{get_full_title(e)}' (superseded by '{new_flow_title}')"
            )
        osw_instance.delete_entity(
            stale_entities,
            comment="Replaced by updated PrefectFlow deployment",
        )

    osw_instance.store_entity(
        OSW.StoreEntityParam(entities=[this_tool, this_flow], overwrite=True)
    )

    # build parameters template from flow function signature
    # includes all fields so users can see and customize them
    import inspect
    import json

    sig = inspect.signature(flow.fn)
    params_template = {}
    for name, param in sig.parameters.items():
        if param.default is not inspect.Parameter.empty:
            default = param.default
            if hasattr(default, "dict"):
                default = default.dict()
            params_template[name] = default
        elif param.annotation is not inspect.Parameter.empty:
            ann = param.annotation
            if hasattr(ann, "__fields__"):
                # pydantic model — show all fields with defaults or placeholders
                field_values = {}
                for fname, field in ann.__fields__.items():
                    if field.default_factory is not None:
                        field_values[fname] = f"<{fname}>"
                    elif field.default is not None:
                        field_values[fname] = field.default
                    else:
                        field_values[fname] = f"<{fname}>"
                params_template[name] = field_values
            else:
                params_template[name] = f"<{name}>"
        else:
            params_template[name] = f"<{name}>"

    params_json = json.dumps(params_template, default=str)

    # replace known values with wiki/mustache template variables
    wiki_var_replacements = {
        '"<uuid>"': '"{{uuid}}"',
        '"<subject>"': '"{{FULLPAGENAME}}"',
        '"<osw_domain>"': '"{{SERVERNAME}}"',
    }
    for placeholder, wiki_var in wiki_var_replacements.items():
        params_json = params_json.replace(placeholder, wiki_var)

    # write usage template snippet to the Software page's main slot
    snippet = (
        '<div class="PrefectStatusBadge" data-config=\'{'
        ' "uuid": "{{uuid}}",'
        f' "workflow_title": "{software_title}",'
        ' "parent": "{{FULLPAGENAME}}",'
        f' "parameters": {params_json}'
        "}'></div>"
    )
    usage_text = (
        "== Usage ==\n"
        "Insert this snippet in a page to trigger this workflow:\n"
        "<pre>\n"
        f"{snippet}\n"
        "</pre>\n"
    )
    import logging

    logging.getLogger(__name__).debug(
        "Writing usage template to '%s':\n%s", software_title, snippet
    )

    page = osw_instance.site.get_page(
        WtSite.GetPageParam(titles=[software_title])
    ).pages[0]
    page.set_slot_content(slot_key="main", content=usage_text)
    page.edit()


async def _deploy(param: DeployParam):
    """programmatic deployment supported in newer prefect versions
    This should become part of osw-python
    """

    _original_api_url = None
    _original_httpx_init = None
    gateway_url = param.public_url or environ.get("PREFECT_API_URL", "")
    if _is_apigateway_url(gateway_url) and param.osw is not None:
        _original_api_url = environ.get("PREFECT_API_URL")
        environ["PREFECT_API_URL"] = gateway_url
        _gw_transport = ApiGatewayTransport(
            gateway_url=gateway_url,
            mw_site=param.osw.site.mw_site,
        )
        # Patch httpx.AsyncClient to auto-inject our transport when
        # the base_url is an ApiGateway URL. One patch covers ALL
        # Prefect client instances regardless of how they're created.
        _original_httpx_init = httpx.AsyncClient.__init__

        def _patched_httpx_init(self, *args, **kwargs):
            base = str(kwargs.get("base_url", ""))
            if _is_apigateway_url(base) and "transport" not in kwargs:
                kwargs["transport"] = _gw_transport
            _original_httpx_init(self, *args, **kwargs)

        httpx.AsyncClient.__init__ = _patched_httpx_init

        # Auto-install .pth hook so Prefect subprocesses also get patched
        _pth_target = os.path.join(_get_site_packages(), _PTH_FILENAME)
        if not os.path.exists(_pth_target):
            install_gateway_hook()

    deployments = []

    for deploy_config in param.deployments:
        flow: Flow = deploy_config.flow
        # Set deployment name if not provided
        if deploy_config.name is None or deploy_config.name == "":
            deploy_config.name = flow.name + "-deployment"

        # Match valid args of flow.to_deployment and deploy_config
        kwargs = match_func_model_args(func=flow.to_deployment, model=deploy_config)
        # Set config via matching flow.to_deployment arguments
        config = await flow.to_deployment(**kwargs)
        await config.apply()  # returns the deployment_uuid

        deployments.append(config)

        # Register flow on OSW if an instance is provided
        if param.osw is not None:
            await register_flow(
                osw_instance=param.osw,
                flow=flow,
                namespace_uuid=param.namespace_uuid,
                public_url=param.public_url,
            )

    try:
        await serve(*deployments)
    finally:
        # Restore patched httpx.AsyncClient.__init__
        if _original_httpx_init is not None:
            httpx.AsyncClient.__init__ = _original_httpx_init
        # Restore original PREFECT_API_URL if we overrode it
        if _original_api_url is not None:
            environ["PREFECT_API_URL"] = _original_api_url
        elif _is_apigateway_url(gateway_url):
            environ.pop("PREFECT_API_URL", None)


def deploy(param: DeployParam):
    """Function to serve configured flows as deployments by python version."""
    if sys.version_info >= (3, 11):
        with asyncio.Runner() as runner:
            runner.run(_deploy(param))
    else:
        asyncio.run(_deploy(param))


# # ------------------------------- TEST -------------------------------
# from prefect import flow


# @flow
# def osw_python_test_flow_to_deploy():
#     """Example flow to be deployed"""
#     print(f"Execution of example: {osw_python_test_flow_to_deploy.__name__}!")


# if __name__ == "__main__":
#     deploy(
#         DeployParam(
#             deployments=[
#                 DeployConfig(
#                     flow=osw_python_test_flow_to_deploy,
#                     name="osw-python-deployment-test",
#                     description="Deployment of osw-python test flow",
#                     version="0.0.1",
#                     tags=["osw-python", "example-deploy-flow"],
#                 )
#             ],
#             # remove_existing_deployments=True,
#         )
#     )
