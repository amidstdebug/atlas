import { createApp } from 'vue';
import App from './App.vue';
import ElementPlus from 'element-plus';
import 'element-plus/dist/index.css';

// Import all Element Plus icons
import * as ElementPlusIconsVue from '@element-plus/icons-vue';

const app = createApp(App);

// Use Element Plus
app.use(ElementPlus);

// Register all Element Plus icons globally
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component);
}

app.mount('#app');
