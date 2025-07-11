<script setup lang="ts">
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert'
import { AlertTriangle, Loader2, Moon, Sun } from 'lucide-vue-next'

definePageMeta({
  middleware: 'guest',
  layout: false
})

const authStore = useAuthStore()
const { $colorMode } = useNuxtApp()

const loginForm = ref({
  user_id: '',
  password: ''
})

const isLoading = ref(false)
const errorMessage = ref('')

async function onSubmit() {
  if (!loginForm.value.user_id || !loginForm.value.password) {
    errorMessage.value = 'Please enter both username and password'
    return
  }

  isLoading.value = true
  errorMessage.value = ''

  const result = await authStore.login(loginForm.value)

  if (result?.success) {
    await navigateTo('/dashboard')
  } else {
    errorMessage.value = result?.error || 'Login failed. Please try again.'
  }

  isLoading.value = false
}

useHead({
  title: 'Login - ATLAS'
})
</script>

<template>
  <div class="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950 tech-grid-bg">
    <!-- Theme Toggle -->
    <div class="absolute top-6 right-6 z-10">
      <Button
        variant="ghost"
        size="icon"
        class="rounded-full bg-background/80 backdrop-blur-sm border border-border/50 shadow-lg hover:shadow-xl transition-all duration-200"
        @click="$colorMode.preference = $colorMode.value === 'dark' ? 'light' : 'dark'"
      >
        <Sun v-if="$colorMode.value === 'dark'" class="h-4 w-4" />
        <Moon v-else class="h-4 w-4" />
      </Button>
    </div>

    <div class="min-h-screen flex items-center justify-center p-6">
      <Card class="w-full max-w-md border-0 shadow-2xl bg-card/80 backdrop-blur-xl">
        <CardHeader class="text-center pb-5">
          <!-- Logo -->
          <div class="mx-auto h-16 flex items-center justify-center">
            <!-- light theme → dark logo | dark theme → light logo -->
            <img
              v-if="$colorMode.value === 'dark'"
              src="/ATLAS_light.png"
              alt="ATLAS logo (light)"
              class="h-16"
            />
            <img
              v-else
              src="/ATLAS_dark.png"
              alt="ATLAS logo (dark)"
              class="h-16"
            />
		  </div>

          <div class="space-y-2">
            <CardTitle class="text-lg font-bold">Air Traffic Control Analysis System</CardTitle>
            <CardDescription class="text-base">
              Sign in to access your dashboard
            </CardDescription>
          </div>
        </CardHeader>

        <CardContent class="space-y-6">
          <form @submit.prevent="onSubmit" class="space-y-6">
            <div class="space-y-2">
              <Label for="username" class="text-sm font-medium">Username</Label>
              <Input
                id="username"
                v-model="loginForm.user_id"
                type="text"
                placeholder="Enter your username"
                :disabled="isLoading"
                class="h-12 rounded-xl border-border/50 bg-background/50 backdrop-blur-sm focus:bg-background transition-all duration-200"
                required
              />
            </div>

            <div class="space-y-2">
              <Label for="password" class="text-sm font-medium">Password</Label>
              <Input
                id="password"
                v-model="loginForm.password"
                type="password"
                placeholder="Enter your password"
                :disabled="isLoading"
                class="h-12 rounded-xl border-border/50 bg-background/50 backdrop-blur-sm focus:bg-background transition-all duration-200"
                required
              />
            </div>

            <Transition
              enter-active-class="transition-all duration-300 ease-out"
              enter-from-class="opacity-0 -translate-y-2"
              enter-to-class="opacity-100 translate-y-0"
              leave-active-class="transition-all duration-200 ease-in"
              leave-from-class="opacity-100 translate-y-0"
              leave-to-class="opacity-0 -translate-y-2"
            >
              <Alert v-if="errorMessage" variant="destructive" class="rounded-xl">
                <AlertTriangle class="h-4 w-4" />
                <AlertDescription>
                  {{ errorMessage }}
                </AlertDescription>
              </Alert>
            </Transition>

            <Button
              type="submit"
              class="w-full h-12 rounded-xl bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 shadow-lg hover:shadow-xl transition-all duration-200 text-white font-medium"
              :disabled="isLoading"
            >
              <Loader2 v-if="isLoading" class="mr-2 h-4 w-4 animate-spin" />
              {{ isLoading ? 'Signing in...' : 'Sign In' }}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  </div>
</template>