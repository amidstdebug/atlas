<script setup lang="ts">
// Redirect to dashboard on page load
await navigateTo('/dashboard', { replace: true })
</script>

<template>
  <div class="min-h-screen flex items-center justify-center">
    <div class="text-center">
      <div class="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto"></div>
      <p class="mt-2 text-gray-600">Redirecting...</p>
    </div>
  </div>
</template>