
//import {Vue} from "https://esm.sh/vue@3";
import { createApp, ref } from "vue"; //"https://esm.sh/vue@3";
//import {Vue} from "https://unpkg.com/vue@3/dist/vue.global.js"
//import {JSONEditor} from "https://esm.sh/@json-editor/json-editor@latest"
//import {JSONEditor} from "@json-editor/json-editor"
//import {JSONEditor} from "jsoneditor"
import JsonEditorComponent from "@/jsoneditor.vue" //"jsoneditor.js"
import "@/jsoneditor_component.less"


//export function render() {
export function render({ model, el }) {
  const e = document.createElement('div')
  e.setAttribute("id", "jsoneditor-container")
  el.append(e);
  console.log("Create App");
  //debugger
  let options = model.get("options");
  options = options || {
    "theme": 'bootstrap4',
    "iconlib": 'spectre',
    schema: {
      "title": "Editor Test",
      "required": ["test"],
      "properties": {"test": {"type": "string"}}},
    //   startval: this.data
  }
  const app = createApp(JsonEditorComponent, {
    options: options,
    onChange: (value) => {
      console.log("CHANGE", value);
      model.set("value", value);
      model.save_changes();
    }
  });
  app.mount(el);
  //return e;
}
