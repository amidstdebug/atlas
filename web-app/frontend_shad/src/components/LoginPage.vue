<template>
  <div class="flex justify-center items-center min-h-screen bg-gray-100">
    <Card class="w-full max-w-md p-8">
      <h2 class="text-center text-2xl font-semibold mb-6">ATLAS - Login</h2>
      <form @submit.prevent="onSubmit">
        <div class="mb-4">
          <Label for="username">Username</Label>
          <div class="flex items-center border rounded p-2">
            <Input
                v-model="loginForm.user_id"
                type="text"
                id="username"
                placeholder="Username"
                class="w-full outline-none"
            />
          </div>
        </div>
        <div class="mb-4">
          <Label for="password">Password</Label>
          <div class="flex items-center border rounded p-2">
            <Input
                v-model="loginForm.password"
                type="password"
                id="password"
                placeholder="Password"
                class="w-full outline-none"
            />
          </div>
        </div>
        <Button type="submit" class="w-full bg-blue-600 text-white py-2 rounded hover:bg-blue-700">
          Login
        </Button>
      </form>
    </Card>
  </div>
</template>

<script setup>
import {ref} from 'vue';
import {useRouter} from 'vue-router';
import {Card} from '@/components/ui/card';
import {Input} from '@/components/ui/input';
import {Button} from '@/components/ui/button';
import {Label} from '@/components/ui/label';
// import {LockIcon} from '@/components/ui/lockicon';

// import { Card } from '@/components/ui/card'
import apiClient from '@/router/apiClient';
import Cookies from 'js-cookie';

const loginForm = ref({
  user_id: '',
  password: '',
});

const router = useRouter();

const onSubmit = async () => {
  try {
    const response = await apiClient.post('/auth/login', loginForm.value);
    const token = response.data.token;
    Cookies.set('auth_token', token);
    router.push('/');
  } catch (error) {
    console.error('Login failed:', error);
    alert('Login failed, please try again.');
  }
};
</script>

<style scoped>
/* Additional styles if needed */
</style>