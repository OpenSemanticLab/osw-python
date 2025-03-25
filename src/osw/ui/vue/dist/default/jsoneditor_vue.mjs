import { openBlock as n, createElementBlock as i, createElementVNode as l, toDisplayString as p, createApp as c } from "vue";
const _ = (e, t) => {
  const o = e.__vccOpts || e;
  for (const [s, a] of t)
    o[s] = a;
  return o;
}, d = {
  name: "dm-json-form3",
  components: {},
  props: {
    options: {
      type: Object
    },
    schema: {
      type: Object
    },
    data: {
      type: Object
    },
    enabled: {
      type: Boolean,
      default: !0
    },
    title: {
      type: String,
      default: ""
    }
  },
  async mounted() {
    await import("jsoneditor");
    const e = { theme: "bootstrap4", iconlib: "spectre", remove_button_labels: !0, ajax: !0, ajax_cache_responses: !1, disable_collapse: !1, disable_edit_json: !0, disable_properties: !1, use_default_values: !0, required_by_default: !1, display_required_only: !0, show_opt_in: !1, show_errors: "always", disable_array_reorder: !1, disable_array_delete_all_rows: !1, disable_array_delete_last_row: !1, keep_oneof_values: !1, no_additional_properties: !0, case_sensitive_property_search: !1, ...this.options };
    console.warn("Options: ", e);
    var t = new JSONEditor(this.$el, e);
    console.warn("Editor: ", this.editor), t.on("ready", () => {
      this.enabled === !1 && t.disable();
    }), t.on("change", () => {
      this.$emit("change", t.getValue());
    });
  },
  /*watch: {
    data(value) { this.editor.setValue(value) }
  },*/
  emits: ["onChange"]
}, u = {
  ref: "jsoneditor",
  id: "jsoneditor",
  class: "bootstrap-wrapper"
};
function f(e, t, o, s, a, r) {
  return n(), i("div", u, [
    l("h2", null, p(o.title), 1)
  ], 512);
}
const b = /* @__PURE__ */ _(d, [["render", f]]);
function m({ model: e, el: t }) {
  const o = document.createElement("div");
  o.setAttribute("id", "jsoneditor-container"), t.append(o), console.log("Create App");
  let s = e.get("options");
  s = s || {
    theme: "bootstrap4",
    iconlib: "spectre",
    schema: {
      title: "Editor Test",
      required: ["test"],
      properties: { test: { type: "string" } }
    }
    //   startval: this.data
  }, c(b, {
    options: s,
    onChange: (r) => {
      console.log("CHANGE", r), e.set("value", r), e.save_changes();
    }
  }).mount(t);
}
export {
  m as render
};
