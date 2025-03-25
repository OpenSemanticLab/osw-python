#! pip install nicegui pyscss
from pathlib import Path

from nicegui import app, ui

import osw.model.entity as model
from osw.ui.nicegui.jsoneditor import OswEditor


def change(data):
    print(data)


# jsoneditor = JsonEditor()
jsoneditor = OswEditor(entity=model.Item)
ui.button("Clear")  # , on_click=jsoneditor.clear)

# see https://github.com/zauberzeug/nicegui/issues/4177
bundled_assets_dir = Path(__file__).parent.parent / "vue" / "dist" / "default"
print(bundled_assets_dir)
css_name = "bootstrap_scoped.css"
app.add_static_file(
    local_file=bundled_assets_dir / "jsoneditor_vue.css",
    url_path="/" + css_name,
)
ui.add_head_html(
    rf'<link rel="stylesheet" href="/{css_name}">',
    shared=True,
)

ui.run()
# ui.run(reload=False, native=True)
