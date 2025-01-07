// vite.config.js
import path from 'path'
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import anywidget from "@anywidget/vite";
//import { dynamicImportWithImportMap } from '@kanamone/vite-plugin-dynamic-import-with-import-map'
import { rollupImportMapPlugin } from "rollup-plugin-import-map";
import alias from '@rollup/plugin-alias';

export default defineConfig(({ mode }) => {
    return {
        build: {
            outDir: "dist/anywidget",
            lib: {
                name: 'jsoneditor_vue',
                fileName: 'jsoneditor_vue',
                //entry: ["src/jsoneditor.vue"],
                entry: ["src/jsoneditor_component.js"],
                formats: ["es"],
            },
            rollupOptions: {
                // External packages that should not be bundled into your library.
                //external: ["vue", "@json-editor/json-editor", "jsoneditor"],
                output: {
                    assetFileNames: "jsoneditor_vue.[ext]",
                    globals: {
                        vue: "vue",
                        jsoneditor: "@json-editor/json-editor"
                    },
                    manualChunks(file) {
                        return 'index'
                    }
                },
                plugins: [
                    // rollupImportMapPlugin({
                    //     "imports": {
                    //         "vue": "https://esm.sh/vue@3",
                    //         //"@json-editor/json-editor": "https://esm.sh/@json-editor/json-editor@latest", // works with `import {JSONEditor} from "@json-editor/json-editor"`
                    //         //"@json-editor/json-editor": "https://cdn.jsdelivr.net/npm/@json-editor/json-editor@latest/dist/jsoneditor.min.js", // works with `import("@json-editor/json-editor")`
                    //         "jsoneditor": "https://cdn.jsdelivr.net/npm/@json-editor/json-editor@latest/dist/jsoneditor.min.js", // works with `import("jsoneditor")`
                    //         //"jsoneditor": "https://esm.sh/@json-editor/json-editor@latest", // works with `import {JSONEditor} from "jsoneditor"`
                    //     },
                    // }),
                    alias({
                        entries: [
                          { find: 'jsoneditor', replacement: 'https://esm.sh/@json-editor/json-editor@latest' },
                          //{ find: 'jsoneditor', replacement: '@json-editor/json-editor' },
                        ]
                      })
                ],
            }
        },
        plugins: [
            vue(),
            anywidget(),
            /*rollupImportMapPlugin({
                "imports": {
                    "vue": "https://esm.sh/vue@3",
                    //"@json-editor/json-editor": "https://esm.sh/@json-editor/json-editor@latest", // works with `import {JSONEditor} from "@json-editor/json-editor"`
                    //"@json-editor/json-editor": "https://cdn.jsdelivr.net/npm/@json-editor/json-editor@latest/dist/jsoneditor.min.js", // works with `import("@json-editor/json-editor")`
                    "jsoneditor": "https://cdn.jsdelivr.net/npm/@json-editor/json-editor@latest/dist/jsoneditor.min.js", // works with `import("jsoneditor")`
                },
            }),*/
        ],
        // https://stackoverflow.com/questions/74120349/building-bundle-for-web-in-vite
        define: {
            'process.env.NODE_ENV': JSON.stringify(mode),
        },
        resolve: {
            alias: {
                '@/': `${path.resolve(__dirname, 'src')}/`
            },
        },
    }
});
