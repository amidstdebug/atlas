// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
    compatibilityDate: '2024-11-01',
    devtools: { enabled: true },
    modules: [
      '@nuxtjs/tailwindcss',
      'shadcn-nuxt',
      '@nuxtjs/color-mode',
      '@nuxtjs/google-fonts',
      '@nuxt/icon'
    ],
    googleFonts: {
        families: {
            Inter: '200..700',
        }
    },
    lucide: {
      namePrefix: 'Icon'
    }
})
