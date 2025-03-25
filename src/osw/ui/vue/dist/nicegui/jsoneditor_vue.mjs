import { openBlock as r, createElementBlock as n, createElementVNode as l, toDisplayString as i } from "vue";
const _ = (t, e) => {
  const o = t.__vccOpts || t;
  for (const [s, a] of e)
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
    const t = { theme: "bootstrap4", iconlib: "spectre", remove_button_labels: !0, ajax: !0, ajax_cache_responses: !1, disable_collapse: !1, disable_edit_json: !0, disable_properties: !1, use_default_values: !0, required_by_default: !1, display_required_only: !0, show_opt_in: !1, show_errors: "always", disable_array_reorder: !1, disable_array_delete_all_rows: !1, disable_array_delete_last_row: !1, keep_oneof_values: !1, no_additional_properties: !0, case_sensitive_property_search: !1, ...this.options };
    console.warn("Options: ", t);
    var e = new JSONEditor(this.$el, t);
    console.warn("Editor: ", this.editor), e.on("ready", () => {
      this.enabled === !1 && e.disable();
    }), e.on("change", () => {
      this.$emit("change", e.getValue());
    });
  },
  /*watch: {
    data(value) { this.editor.setValue(value) }
  },*/
  emits: ["onChange"]
}, c = {
  ref: "jsoneditor",
  id: "jsoneditor",
  class: "bootstrap-wrapper"
};
function p(t, e, o, s, a, f) {
  return r(), n("div", c, [
    l("h2", null, i(o.title), 1)
  ], 512);
}
const b = /* @__PURE__ */ _(d, [["render", p]]);
export {
  b as default
};
