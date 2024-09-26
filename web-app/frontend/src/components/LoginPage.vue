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
import apiClient from '../router/apiClient'; // Import the apiClient
import Cookies from 'js-cookie';

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
      try {
        // Use apiClient to make the login request
        const response = await apiClient.post('/auth/login', this.loginForm);
        const token = response.data.token;
        Cookies.set('auth_token', token); // Store the token in cookies
        this.$router.push('/'); // Redirect to the main app
      } catch (error) {
        console.error('Login failed:', error);
        this.$message.error('Login failed, please try again.');
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
