<template>
  <div class="ner-keyword-manager">
    <div class="bg-white dark:bg-gray-800 rounded-lg shadow-lg p-6">
      <!-- Header -->
      <div class="flex items-center justify-between mb-6">
        <h2 class="text-2xl font-bold text-gray-900 dark:text-white">
          NER Keywords Manager
        </h2>
        <div class="flex items-center space-x-2">
          <div class="w-3 h-3 rounded-full" :class="encryptionStatus ? 'bg-green-500' : 'bg-red-500'"></div>
          <span class="text-sm text-gray-600 dark:text-gray-400">
            {{ encryptionStatus ? 'Encrypted' : 'Not Initialized' }}
          </span>
        </div>
      </div>

      <!-- Statistics Cards -->
      <div class="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <div class="bg-blue-50 dark:bg-blue-900/20 p-4 rounded-lg">
          <div class="text-2xl font-bold text-blue-600 dark:text-blue-400">
            {{ stats.default_keywords_count || 0 }}
          </div>
          <div class="text-sm text-blue-600 dark:text-blue-400">Default Keywords</div>
        </div>
        <div class="bg-green-50 dark:bg-green-900/20 p-4 rounded-lg">
          <div class="text-2xl font-bold text-green-600 dark:text-green-400">
            {{ stats.user_keywords_count || 0 }}
          </div>
          <div class="text-sm text-green-600 dark:text-green-400">User Keywords</div>
        </div>
        <div class="bg-purple-50 dark:bg-purple-900/20 p-4 rounded-lg">
          <div class="text-2xl font-bold text-purple-600 dark:text-purple-400">
            {{ stats.total_keywords_count || 0 }}
          </div>
          <div class="text-sm text-purple-600 dark:text-purple-400">Total Keywords</div>
        </div>
      </div>

      <!-- Encryption Initialization (if not initialized) -->
      <div v-if="!encryptionStatus" class="mb-6 p-4 bg-yellow-50 dark:bg-yellow-900/20 rounded-lg border border-yellow-200 dark:border-yellow-800">
        <h3 class="text-lg font-semibold text-yellow-800 dark:text-yellow-200 mb-3">
          Initialize Encryption
        </h3>
        <p class="text-sm text-yellow-700 dark:text-yellow-300 mb-4">
          Set up encryption to securely store your custom NER keywords. The password will be used to encrypt/decrypt your keywords.
        </p>
        <div class="flex space-x-3">
          <input
            v-model="initPassword"
            type="password"
            placeholder="Enter encryption password (min 6 chars)"
            class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
            @keyup.enter="initializeEncryption"
          >
          <button
            @click="initializeEncryption"
            :disabled="!initPassword || initPassword.length < 6 || loading"
            class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <span v-if="loading">Initializing...</span>
            <span v-else>Initialize</span>
          </button>
        </div>
      </div>

      <!-- Keywords Management (if initialized) -->
      <div v-if="encryptionStatus" class="space-y-6">
        <!-- Add Keywords Section -->
        <div class="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
          <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-3">
            Add Keywords
          </h3>
          <div class="space-y-3">
            <textarea
              v-model="newKeywords"
              placeholder="Enter keywords (one per line or comma-separated)"
              rows="3"
              class="w-full px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
            ></textarea>
            <div class="flex space-x-3">
              <input
                v-model="password"
                type="password"
                placeholder="Enter your encryption password"
                class="flex-1 px-3 py-2 border border-gray-300 dark:border-gray-600 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 dark:bg-gray-700 dark:text-white"
                @keyup.enter="addKeywords"
              >
              <button
                @click="addKeywords"
                :disabled="!newKeywords.trim() || !password || loading"
                class="px-4 py-2 bg-green-600 text-white rounded-md hover:bg-green-700 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                <span v-if="loading">Adding...</span>
                <span v-else>Add Keywords</span>
              </button>
            </div>
          </div>
        </div>

        <!-- Current User Keywords -->
        <div class="bg-gray-50 dark:bg-gray-700/50 p-4 rounded-lg">
          <div class="flex items-center justify-between mb-3">
            <h3 class="text-lg font-semibold text-gray-900 dark:text-white">
              Your Keywords ({{ userKeywords.length }})
            </h3>
            <button
              v-if="userKeywords.length > 0"
              @click="refreshKeywords"
              class="px-3 py-1 text-sm bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-md hover:bg-blue-200 dark:hover:bg-blue-900/50"
            >
              Refresh
            </button>
          </div>
          
          <div v-if="userKeywords.length === 0" class="text-gray-500 dark:text-gray-400 text-center py-4">
            No user keywords added yet
          </div>
          
          <div v-else class="space-y-2 max-h-40 overflow-y-auto">
            <div
              v-for="keyword in userKeywords"
              :key="keyword"
              class="flex items-center justify-between bg-white dark:bg-gray-700 p-2 rounded border"
            >
              <span class="text-sm text-gray-900 dark:text-white">{{ keyword }}</span>
              <button
                @click="removeKeyword(keyword)"
                class="text-red-500 hover:text-red-700 text-sm"
                title="Remove keyword"
              >
                ✕
              </button>
            </div>
          </div>
          
          <div v-if="userKeywords.length > 0" class="mt-3 pt-3 border-t border-gray-200 dark:border-gray-600">
            <button
              @click="clearAllKeywords"
              class="px-3 py-1 text-sm bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 rounded-md hover:bg-red-200 dark:hover:bg-red-900/50"
            >
              Clear All Keywords
            </button>
          </div>
        </div>
      </div>

      <!-- Status Messages -->
      <div v-if="message" class="mt-4 p-3 rounded-md" :class="messageClass">
        {{ message }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'

// Define API response types
interface ApiResponse {
  success: boolean
  message: string
  data?: any
}

// Reactive data
const encryptionStatus = ref(false)
const stats = ref({
  default_keywords_count: 0,
  user_keywords_count: 0,
  total_keywords_count: 0,
  encryption_initialized: false
})
const userKeywords = ref<string[]>([])
const initPassword = ref('')
const password = ref('')
const newKeywords = ref('')
const loading = ref(false)
const message = ref('')
const messageType = ref<'success' | 'error' | 'info'>('info')

// Computed
const messageClass = computed(() => {
  switch (messageType.value) {
    case 'success':
      return 'bg-green-100 dark:bg-green-900/30 text-green-700 dark:text-green-300 border border-green-200 dark:border-green-800'
    case 'error':
      return 'bg-red-100 dark:bg-red-900/30 text-red-700 dark:text-red-300 border border-red-200 dark:border-red-800'
    default:
      return 'bg-blue-100 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 border border-blue-200 dark:border-blue-800'
  }
})

// Methods
const showMessage = (msg: string, type: 'success' | 'error' | 'info' = 'info') => {
  message.value = msg
  messageType.value = type
  setTimeout(() => {
    message.value = ''
  }, 5000)
}

const loadStats = async () => {
  try {
    const response = await $fetch<ApiResponse>('/api/ner-keywords/stats')
    if (response.success) {
      stats.value = response.data
      encryptionStatus.value = response.data.encryption_initialized
    }
  } catch (error) {
    console.error('Failed to load stats:', error)
  }
}

const loadUserKeywords = async () => {
  try {
    const response = await $fetch<ApiResponse>('/api/ner-keywords/user')
    if (response.success) {
      userKeywords.value = response.data.keywords || []
    }
  } catch (error) {
    console.error('Failed to load user keywords:', error)
  }
}

const initializeEncryption = async () => {
  if (!initPassword.value || initPassword.value.length < 6) {
    showMessage('Password must be at least 6 characters long', 'error')
    return
  }

  loading.value = true
  try {
    const response = await $fetch<ApiResponse>('/api/ner-keywords/initialize', {
      method: 'POST',
      body: {
        password: initPassword.value
      }
    })

    if (response.success) {
      encryptionStatus.value = true
      stats.value = response.data
      initPassword.value = ''
      showMessage('Encryption initialized successfully!', 'success')
      await loadUserKeywords()
    } else {
      showMessage(response.message || 'Failed to initialize encryption', 'error')
    }
  } catch (error: any) {
    showMessage(error.data?.detail || 'Failed to initialize encryption', 'error')
  }
  loading.value = false
}

const addKeywords = async () => {
  if (!newKeywords.value.trim() || !password.value) {
    showMessage('Please enter keywords and password', 'error')
    return
  }

  // Parse keywords (split by newlines or commas)
  const keywordList = newKeywords.value
    .split(/[\n,]/)
    .map(k => k.trim())
    .filter(k => k.length > 0)

  if (keywordList.length === 0) {
    showMessage('No valid keywords found', 'error')
    return
  }

  loading.value = true
  try {
    const response = await $fetch<ApiResponse>('/api/ner-keywords/add', {
      method: 'POST',
      body: {
        keywords: keywordList,
        password: password.value
      }
    })

    if (response.success) {
      stats.value = response.data
      newKeywords.value = ''
      password.value = ''
      showMessage(response.message, 'success')
      await loadUserKeywords()
    } else {
      showMessage(response.message || 'Failed to add keywords', 'error')
    }
  } catch (error: any) {
    showMessage(error.data?.detail || 'Failed to add keywords', 'error')
  }
  loading.value = false
}

const removeKeyword = async (keyword: string) => {
  loading.value = true
  try {
    const response = await $fetch<ApiResponse>('/api/ner-keywords/remove', {
      method: 'POST',
      body: {
        keywords: [keyword]
      }
    })

    if (response.success) {
      stats.value = response.data
      showMessage(`Removed keyword: ${keyword}`, 'success')
      await loadUserKeywords()
    } else {
      showMessage(response.message || 'Failed to remove keyword', 'error')
    }
  } catch (error: any) {
    showMessage(error.data?.detail || 'Failed to remove keyword', 'error')
  }
  loading.value = false
}

const clearAllKeywords = async () => {
  if (!confirm('Are you sure you want to clear all user keywords? This action cannot be undone.')) {
    return
  }

  loading.value = true
  try {
    const response = await $fetch<ApiResponse>('/api/ner-keywords/clear', {
      method: 'DELETE'
    })

    if (response.success) {
      stats.value = response.data
      userKeywords.value = []
      showMessage('All user keywords cleared', 'success')
    } else {
      showMessage(response.message || 'Failed to clear keywords', 'error')
    }
  } catch (error: any) {
    showMessage(error.data?.detail || 'Failed to clear keywords', 'error')
  }
  loading.value = false
}

const refreshKeywords = async () => {
  await Promise.all([loadStats(), loadUserKeywords()])
  showMessage('Keywords refreshed', 'info')
}

// Lifecycle
onMounted(async () => {
  await loadStats()
  if (encryptionStatus.value) {
    await loadUserKeywords()
  }
})
</script>

<style scoped>
.ner-keyword-manager {
  @apply max-w-4xl mx-auto;
}
</style> 