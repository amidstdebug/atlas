<script setup lang="ts">
import { Button } from '@/components/ui/button'

useHead({
  title: '404 - Page Not Found'
})

const router = useRouter()
</script>

<template>
  <div class="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50 dark:from-slate-950 dark:via-slate-900 dark:to-indigo-950">
    <div class="bg-card/95 backdrop-blur-xl rounded-xl shadow-2xl p-8 w-full max-w-md text-center border border-border/50">
      <h1 class="text-6xl font-bold text-blue-600 dark:text-blue-400 mb-4">404</h1>
      <h2 class="text-2xl text-foreground mb-4">Page Not Found</h2>

      <p class="text-muted-foreground mb-6">
        The page you're looking for doesn't exist or has been moved.
      </p>

      <div class="space-y-3">
        <Button
          @click="router.push('/dashboard')"
          class="w-full"
        >
          Go to Dashboard
        </Button>
      </div>
    </div>
  </div>
</template>