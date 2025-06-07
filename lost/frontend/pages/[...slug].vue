<script setup lang="ts">
// Redirect to error page for any unmatched routes
const router = useRouter()
onMounted(() => {
  router.push('/error')
})
</script>

<template>
  <div></div>
</template> 