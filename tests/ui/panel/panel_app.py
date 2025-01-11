import panel as pn

from osw.ui.panel.anywidget_vite.jsoneditor import JsonEditor


class App(pn.viewable.Viewer):

    def __init__(self, **params):
        super().__init__(**params)

        self.jsoneditor = JsonEditor(height=500, max_width=800)

        self._view = pn.Column(
            self.jsoneditor, pn.pane.JSON(self.jsoneditor.param.value, theme="light")
        )

    def __panel__(self):
        return self._view


if pn.state.served:
    pn.extension(sizing_mode="stretch_width")

    App().servable()

if __name__ == "__main__":
    pn.serve(App().servable())
