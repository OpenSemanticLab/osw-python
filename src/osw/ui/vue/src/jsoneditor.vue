<template>
  <div ref="jsoneditor" id="jsoneditor" class="bootstrap-wrapper">
    <h2>{{title}}</h2>

  </div>
</template>

<script>

export default {
  name: 'dm-json-form3',
  components: {},

  props: {
    options: {
      type: Object,
    },
    schema: {
      type: Object,
    },
    data: {
      type: Object,
    },
    enabled: {
      type: Boolean,
      default: true
    },
    title: {
      type: String,
      default: ""
    },
  },

  async mounted() {
    //debugger;
    // access our input using template refs, then focus
    await import("jsoneditor");
    // this.$options = {
    //   //theme: 'bootstrap4',
    //   //iconlib: 'fontawesome4',
    //   theme: 'tailwind',
    //   //iconlib: 'spectre',
    //   schema: {"properties": {"test": {"type": "string"}}},
    //   startval: this.data
    // }
    console.warn("Options: ", this.options)
    var editor = new JSONEditor(this.$el, this.options);
    console.warn("Editor: ", this.editor)

    editor.on('ready', () => {
      // Now the api methods will be available
      if (this.enabled === false) {
        editor.disable();
      }
    });

    editor.on('change' , () => {
      this.$emit('change' , editor.getValue())
    })

  },


  emits: ['onChange'],
};
</script>

<!-- <style lang="less">
.bootstrap-wrapper {
  @import (less) url('https://cdn.jsdelivr.net/npm/bootstrap@4.6.1/dist/css/bootstrap.min.css');
}
</style> -->
