import tailwindcss from '@tailwindcss/vite'

// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-05-15',
  modules: ['shadcn-nuxt', '@vueuse/nuxt', '@pinia/nuxt', '@nuxtjs/color-mode', '@nuxt/fonts'],
  shadcn: {
    prefix: '',
    componentDir: './components/ui'
  },
  devtools: { enabled: true },
  css: ['~/assets/css/tailwind.css', 'vue-sonner/style.css'],
  
  runtimeConfig: {
    public: {
      baseURL: process.env.BASE_URL || 'http://localhost:5002'
    }
  },

  vite: {
    plugins: [
      tailwindcss(),
    ],
    define: {
      global: 'globalThis',
    }
  },

  colorMode: {
    classSuffix: '',
  },

  build: {
    transpile: [
      'vee-validate',
      'vue-sonner',
    ],
  },

  ssr: false, // For easier audio processing client-side
  
  nitro: {
    experimental: {
      wasm: true
    }
  }
})