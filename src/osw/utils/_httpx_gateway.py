"""Auto-patches httpx for ApiGateway routing in Prefect subprocesses.

Activated by osw-httpx-gateway.pth in site-packages. Only patches if
PREFECT_API_URL contains an ApiGateway URL pattern. Login is lazy —
no network calls at import time. All ``osw`` imports are deferred to
first request so the hook works even before editable installs are on
sys.path.
"""

import os


def _install():
    api_url = os.environ.get("PREFECT_API_URL", "")
    if "/rest.php/apigateway/" not in api_url:
        return

    if not os.environ.get("OSW_SERVER"):
        return

    try:
        import httpx
    except ImportError:
        return

    class _LazyApiGatewayTransport(httpx.AsyncBaseTransport):
        """Wraps ApiGatewayTransport with lazy MW login on first request."""

        def __init__(self, gateway_url):
            self._gateway_url = gateway_url
            self._inner = None

        def _ensure_initialized(self):
            if self._inner is not None:
                return
            # Deferred import — osw may not be on sys.path at .pth time
            from osw.utils.workflow import ApiGatewayTransport, connect

            osw_instance = connect()
            mw_site = osw_instance.site.mw_site

            def _relogin():
                cred = osw_instance.site._cred_mngr.get_credential(
                    osw_instance.site._iri
                )
                mw_site.login(username=cred.username, password=cred.password)

            self._inner = ApiGatewayTransport(
                gateway_url=self._gateway_url,
                mw_site=mw_site,
                relogin_cb=_relogin,
            )

        async def handle_async_request(self, request):
            self._ensure_initialized()
            return await self._inner.handle_async_request(request)

    _transport = _LazyApiGatewayTransport(api_url)
    _original_init = httpx.AsyncClient.__init__

    def _patched_init(self, *args, **kwargs):
        base = str(kwargs.get("base_url", ""))
        if "/rest.php/apigateway/" in base and "transport" not in kwargs:
            kwargs["transport"] = _transport
        _original_init(self, *args, **kwargs)

    httpx.AsyncClient.__init__ = _patched_init


_install()
