import json
from pathlib import Path

import panel as pn
import param
from panel.custom import AnyWidgetComponent

pn.extension()

bundled_assets_dir = Path(__file__).parent.parent.parent / "vue" / "dist" / "default"


# class JsonEditor(JSComponent):
class JsonEditor(AnyWidgetComponent):

    _esm = (bundled_assets_dir / "jsoneditor_vue.mjs").read_text()

    _stylesheets = [
        # bundled_assets_dir / "style.css",
        # v5 does not work properly:
        "https://cdn.jsdelivr.net/npm/bootstrap@4/dist/css/bootstrap.min.css",
        # does not work:
        # 'https://use.fontawesome.com/releases/v5.12.1/css/all.css',
        "https://unpkg.com/spectre.css/dist/spectre-icons.min.css",
    ]
    _importmap = {
        "imports": {
            "vue": "https://esm.sh/vue@3",
            # works with `import {JSONEditor} from "@json-editor/json-editor"`:
            # "@json-editor/json-editor": "https://esm.sh/@json-editor/json-editor@latest",
            # works with `import("@json-editor/json-editor")`:
            # "@json-editor/json-editor": (
            #   "https://cdn.jsdelivr.net/npm/@json-editor/json-editor",
            #   "@latest/dist/jsoneditor.min.js"
            # ),
            # works with `import("jsoneditor")`:
            "jsoneditor": (
                "https://cdn.jsdelivr.net/npm/@json-editor/json-editor",
                "@latest/dist/jsoneditor.min.js",
            ),
        }
    }
    # __javascript__= [
    #     "https://cdn.jsdelivr.net/npm/vue@2/dist/vue.js",
    #     "https://unpkg.com/bootstrap-vue@latest/dist/bootstrap-vue.min.js",
    #     "https://cdn.jsdelivr.net/npm/@json-editor/json-editor@latest/dist/jsoneditor.min.js"
    # ]
    value = param.Dict()
    options = param.Dict(
        default={
            "theme": "bootstrap4",
            # "iconlib": 'fontawesome5',
            "iconlib": "spectre",
            "schema": {"properties": {"testxy": {"type": "string"}}},
        }
    )

    encoder = param.ClassSelector(
        class_=json.JSONEncoder,
        is_instance=False,
        doc="""
    Custom JSONEncoder class used to serialize objects to JSON string.""",
    )

    def get_value(self):
        json_str = json.dumps(self.value, cls=self.encoder)
        return json.loads(json_str)


class OswEditor(JsonEditor):

    options = param.Dict(
        default={
            "theme": "bootstrap4",
            # "iconlib": 'fontawesome5',
            "iconlib": "spectre",
            "schema": {"properties": {"testxy": {"type": "string"}}},
        }
    )


if __name__ == "__main__":

    jsoneditor = JsonEditor(height=500, max_width=800)
    pn.serve(
        pn.Column(
            jsoneditor, pn.pane.JSON(jsoneditor.param.value, theme="light")
        ).servable()
    )

    jsoneditor.get_value()
