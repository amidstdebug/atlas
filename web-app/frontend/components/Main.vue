<script setup lang="ts">
// Set page title
useHead({
  title: 'ATLAS - Automated Transcription & Language Analysis System',
  meta: [
    { name: 'description', content: 'Advanced transcription and analysis platform for air traffic control and meeting documentation' }
  ]
})

// Ensure stores are available globally
const authStore = useAuthStore()
</script>

<template>
  <div>
    <NuxtRouteAnnouncer />
    <NuxtLayout>
      <NuxtPage />
    </NuxtLayout>
  </div>
</template>