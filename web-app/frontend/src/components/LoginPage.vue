<template>
  <div class="login-container">
    <el-card class="login-card">
      <h2 class="login-title">ATLAS - Login</h2>
      <el-form ref="loginForm" :model="loginForm" @submit.prevent="onSubmit">
        <el-form-item>
          <el-input
            v-model="loginForm.user_id"
            placeholder="Username"
          >
            <template #prefix>
              <el-icon><User /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-input
            type="password"
            v-model="loginForm.password"
            placeholder="Password"
          >
            <template #prefix>
              <el-icon><Lock /></el-icon>
            </template>
          </el-input>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" class="login-button" @click="onSubmit" round>Login</el-button>
        </el-form-item>
      </el-form>
    </el-card>
  </div>
</template>

<script>
import { User, Lock } from '@element-plus/icons-vue';
import { login } from '../router/apiClient'; // Import the login helper
import { ElMessage, ElLoading } from 'element-plus';

export default {
  name: 'LoginPage',
  components: {
    User,
    Lock,
  },
  data() {
    return {
      loginForm: {
        user_id: '',
        password: '',
      },
    };
  },
  mounted() {
    // Change the title of the tab when the component is mounted
    document.title = 'Login';
  },
  methods: {
    async onSubmit() {
      if (!this.loginForm.user_id || !this.loginForm.password) {
        ElMessage.warning('Please enter both username and password');
        return;
      }
      
      const loading = ElLoading.service({
        lock: true,
        text: 'Logging in...',
        background: 'rgba(0, 0, 0, 0.7)'
      });
      
      try {
        // Use the login helper function
        const result = await login(this.loginForm.user_id, this.loginForm.password);
        
        if (result.success) {
          ElMessage.success('Login successful');
          this.$router.push('/'); // Redirect to the main app
        } else {
          ElMessage.error(result.error || 'Login failed. Please try again.');
        }
      } catch (error) {
        console.error('Login failed:', error);
        ElMessage.error('An unexpected error occurred. Please try again.');
      } finally {
        loading.close();
      }
    },
  },
};
</script>

<style scoped>
.login-container {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  background-color: #f2f2f2;
}

.login-card {
  padding: 30px;
  width: 100%;
  max-width: 400px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.login-title {
  text-align: center;
  margin-bottom: 20px;
  font-size: 24px;
  color: #333;
}

.login-button {
  width: 100%;
}

.el-input {
  margin-bottom: 20px;
}
</style>
