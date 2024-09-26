import { createApp } from 'vue';
import App from './App.vue';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';
import * as ElementPlusIconsVue from '@element-plus/icons-vue';
import router from './router/router'; // Import the router
import Cookies from 'js-cookie'; // Import js-cookie for handling cookies

const app = createApp(App);

// Use Element Plus
app.use(ElementPlus);

// Register all Element Plus icons globally
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}

// Use the router
app.use(router);

// Mount the app
app.mount('#app');
