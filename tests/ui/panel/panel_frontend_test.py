# pip install panel pytest pytest-playwright
# playwright install
# pytest panel_frontend_test.py --headed --slowmo 1000

import time

import panel as pn
from panel_app import App
from playwright.sync_api import Page

# pytest ./tests/ui/panel/panel_frontend_test.py --headed --slowmo 1000


def test_component(page: Page, port):

    app = App()
    url = f"http://localhost:{port}"

    server = pn.serve(app, port=port, threaded=True, show=False)
    time.sleep(0.2)

    page.goto(url)
    time.sleep(3)  # wait for page to load

    # print(json.dumps(app.jsoneditor.get_value()))
    assert app.jsoneditor.get_value() == {"testxy": ""}

    # note: css selector for id=root[testxy] needs to escaped,
    # see https://stackoverflow.com/questions/1466103/escape-square-brackets-when-assigning-a-class-name-to-an-element # noqa
    page.locator("#root\\[testxy\\]").fill("test123")
    page.locator("[for=root\\[testxy\\]]").click()
    assert app.jsoneditor.get_value() == {"testxy": "test123"}

    server.stop()
