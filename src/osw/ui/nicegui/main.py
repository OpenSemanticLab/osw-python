#! pip install nicegui pyscss
from nicegui import app, ui

import osw.model.entity as model
from osw.ui.nicegui.jsoneditor import OswEditor


def change(data):
    print(data)


# jsoneditor = JsonEditor()
jsoneditor = OswEditor(entity=model.Item)
ui.button("Clear")  # , on_click=jsoneditor.clear)

# see https://github.com/zauberzeug/nicegui/issues/4177
css_name = "bootstrap_scoped.css"
app.add_static_file(
    local_file="./src/osw/ui/vue/dist/default/jsoneditor_vue.css",
    url_path="/" + css_name,
)
ui.add_head_html(
    rf'<link rel="stylesheet" href="/{css_name}">',
    shared=True,
)

ui.run()
# ui.run(reload=False, native=True)
