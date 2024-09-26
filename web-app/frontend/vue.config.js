const { defineConfig } = require('@vue/cli-service')

module.exports = defineConfig({
  transpileDependencies: true,
  publicPath: '/atlas/',  // Your public path to ensure assets are served from /atlas
  devServer: {
    host: '0.0.0.0',
    port: 7860,  // The port where your dev server is running
    allowedHosts: 'all',
    // client: {
    //   webSocketURL: {
    //     protocol: 'wss',  // Use 'wss' for secure WebSocket over HTTPS
    //     hostname: 'jwong.dev',  // Your domain name
    //     port: 443,  // Use port 443 for HTTPS
    //     pathname: '/ws',  // WebSocket path (optional)
    //   },
    // },
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
