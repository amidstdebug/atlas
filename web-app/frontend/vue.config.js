const { defineConfig } = require('@vue/cli-service')

module.exports = defineConfig({
  transpileDependencies: true,
  publicPath: '/atlas/',  // Your public path to ensure assets are served from /atlas
  devServer: {
    host: '0.0.0.0',
    port: 7860,  // The port where your dev server is running
    allowedHosts: 'all',
    client: {
      webSocketTransport: 'ws',
      progress: true,
      overlay: true
    },
    hot: true,
    liveReload: true,
    https: false,  // Ensure the dev server uses HTTPS
  },
  css: {
    loaderOptions: {
      sass: {
        additionalData: `@import "@/styles/_variables.scss";`
      }
    }
  },
});
