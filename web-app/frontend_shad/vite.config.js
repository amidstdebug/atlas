import {fileURLToPath, URL} from 'node:url'
import vue from '@vitejs/plugin-vue'
import autoprefixer from 'autoprefixer'
import tailwind from 'tailwindcss'
import {defineConfig} from 'vite'

export default defineConfig({
    css: {
        postcss: {
            plugins: [tailwind(), autoprefixer()],
        },
        loaderOptions: {
            sass: {
                additionalData: `@import "@/styles/_variables.scss";`
            }
        }
    },
    plugins: [vue()],
    resolve: {
        alias: {
            '@': fileURLToPath(new URL('./src', import.meta.url))
        }
    },
    server: {
        host: '0.0.0.0',
        port: 7860,
        strictPort: true,
        https: false,
        open: false,
        allowedHosts: 'all',
    },
    // base: '/atlas/'

})