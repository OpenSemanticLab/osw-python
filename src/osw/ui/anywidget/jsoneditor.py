import os
from pathlib import Path

import anywidget
import traitlets

bundled_assets_dir = Path(os.path.abspath("")).parent / "vue" / "dist" / "anywidget"


class JsonEditorWidget(anywidget.AnyWidget):
    # _esm = "jsoneditor.mjs" # works
    # _css =  'https://cdn.jsdelivr.net/npm/bootstrap@4.6.1/dist/css/bootstrap.min.css'
    #   works but conflict with vscode
    # _esm = str(bundled_assets_dir / "jsoneditor_vue.mjs")
    # we need to prefix this static import since the dynamic import
    # import "https://esm.sh/@json-editor/json-editor@latest" does not work
    _esm = (
        'import {JSONEditor} from "https://esm.sh/@json-editor/json-editor@latest"\n'
        + (bundled_assets_dir / "jsoneditor_vue.mjs").read_text()
    )
    # scoped css does not conflict with vscode styling
    _css = (bundled_assets_dir / "jsoneditor_vue.css").read_text()

    value = traitlets.Dict({}).tag(sync=True)
    options = traitlets.Dict({}).tag(sync=True)

    @traitlets.observe("value")
    def _observe_value(self, change):
        pass
        # changes can be handled here
        # print(change["old"])
        # print(change["new"])
