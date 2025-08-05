<template>
  <div class="container mx-auto py-8 px-4">
    <div class="mb-6">
      <h1 class="text-3xl font-bold text-gray-900 dark:text-white mb-2">
        NER Keywords Management
      </h1>
      <p class="text-gray-600 dark:text-gray-400">
        Manage your custom Named Entity Recognition keywords with encrypted storage.
      </p>
    </div>
    
    <NERKeywordManager />
  </div>
</template>

<script setup lang="ts">
// Set page metadata
useHead({
  title: 'NER Keywords - ATLAS',
  meta: [
    { name: 'description', content: 'Manage custom NER keywords with encryption for secure storage.' }
  ]
})

// Require authentication
definePageMeta({
  middleware: 'auth'
})
</script> 