// Build for panel anywidget

// vite.config.js
import path from 'path'
import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
//import anywidget from "@anywidget/vite";

export default defineConfig(({ mode }) => {
    return {
        build: {
            outDir: "dist/default",
            lib: {
                name: 'jsoneditor_vue',
                fileName: 'jsoneditor_vue',
                //entry: ["src/jsoneditor.vue"],
                entry: ["src/jsoneditor_component.js"],
                formats: ["es"],
            },
            rollupOptions: {
                // External packages that should not be bundled into your library.
                external: ["vue", "@json-editor/json-editor", "jsoneditor"],
                output: {
                    assetFileNames: "jsoneditor_vue.[ext]",
                    globals: {
                        vue: "vue",
                        jsoneditor: "@json-editor/json-editor"
                    },
                    // manualChunks(file) {
                    //     // Branch by path string and return JS filename after bundling
                    //     //console.log(file); // full path
                    //     return 'index'
                    // }
                }
            }
        },
        plugins: [
            vue(),
            //anywidget(),
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
