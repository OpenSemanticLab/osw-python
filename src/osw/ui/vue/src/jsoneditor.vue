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
    const options = {...{
      "theme": "bootstrap4",
      "iconlib": "spectre",
      "remove_button_labels": true,
      "ajax": true,
      "ajax_cache_responses": false,
      "disable_collapse": false,
      "disable_edit_json": true,
      "disable_properties": false,
      "use_default_values": true,
      "required_by_default": false,
      "display_required_only": true,
      "show_opt_in": false,
      "show_errors": "always",
      "disable_array_reorder": false,
      "disable_array_delete_all_rows": false,
      "disable_array_delete_last_row": false,
      "keep_oneof_values": false,
      "no_additional_properties": true,
      "case_sensitive_property_search": false,
      //"form_name_root": "this.jsonschema.getSchema().id",
      //"user_language": "this.config.lang"
    }, ...this.options}
    console.warn("Options: ", options)
    var editor = new JSONEditor(this.$el, options);
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
