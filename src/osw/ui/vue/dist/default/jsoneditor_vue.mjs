import { openBlock as i, createElementBlock as a, createElementVNode as p, toDisplayString as c, createApp as d } from "vue";
const l = (t, n) => {
  const e = t.__vccOpts || t;
  for (const [o, s] of n)
    e[o] = s;
  return e;
}, m = {
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
    await import("jsoneditor"), console.warn("Options: ", this.options);
    var t = new JSONEditor(this.$el, this.options);
    console.warn("Editor: ", this.editor), t.on("ready", () => {
      this.enabled === !1 && t.disable();
    }), t.on("change", () => {
      this.$emit("change", t.getValue());
    });
  },
  emits: ["onChange"]
}, h = {
  ref: "jsoneditor",
  id: "jsoneditor",
  class: "bootstrap-wrapper"
};
function f(t, n, e, o, s, r) {
  return i(), a("div", h, [
    p("h2", null, c(e.title), 1)
  ], 512);
}
const u = /* @__PURE__ */ l(m, [["render", f]]);
function _({ model: t, el: n }) {
  const e = document.createElement("div");
  e.setAttribute("id", "jsoneditor-container"), n.append(e), console.log("Create App");
  let o = t.get("options");
  o = o || {
    theme: "bootstrap5",
    iconlib: "fontawesome5",
    schema: { properties: { test: { type: "string" } } }
    //   startval: this.data
  }, d(u, {
    options: o,
    onChange: (r) => {
      console.log("CHANGE", r), t.set("value", r), t.save_changes();
    }
  }).mount(n);
}
export {
  _ as render
};
