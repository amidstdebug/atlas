<template>
  <div class="min-h-screen bg-gray-50 dark:bg-gray-900">
    <!-- Header -->
    <header class="bg-white dark:bg-gray-800 border-b border-gray-200 dark:border-gray-700 top-0 z-10">
      <div class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-4 flex items-center justify-between">
        <div>
          <h1 class="text-xl font-semibold text-gray-900 dark:text-white">NER Keywords</h1>
          <p class="text-sm text-gray-500 dark:text-gray-400">Manage categories and keywords for entity recognition</p>
        </div>
        <div class="flex items-center gap-2">
          <button
            @click="togglePreview"
            class="px-3 py-2 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >
            {{ previewMode ? 'Edit' : 'Preview' }}
          </button>
          <button
            @click="exportKeywords"
            class="px-3 py-2 text-sm bg-gray-100 dark:bg-gray-700 text-gray-700 dark:text-gray-300 rounded-md hover:bg-gray-200 dark:hover:bg-gray-600 transition-colors"
          >
            Export
          </button>
          <label class="px-3 py-2 text-sm bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors cursor-pointer">
            Import
            <input type="file" accept=".json" @change="importKeywords" class="hidden" />
          </label>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
      <!-- Quick Stats -->
      <div v-if="totalKeywords > 0" class="grid grid-cols-3 gap-4 mb-6">
        <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ totalKeywords }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400">Keywords</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ Object.keys(categories).length }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400">Categories</div>
        </div>
        <div class="bg-white dark:bg-gray-800 rounded-lg p-4 border border-gray-200 dark:border-gray-700">
          <div class="text-2xl font-bold text-gray-900 dark:text-white">{{ activeCategories }}</div>
          <div class="text-sm text-gray-500 dark:text-gray-400">Active</div>
        </div>
      </div>

      <!-- Editor/Preview Toggle -->
      <div class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 overflow-hidden">
        <!-- Instructions -->
        <div class="p-4 bg-blue-50 dark:bg-blue-900/20 border-b border-gray-200 dark:border-gray-700">
          <div class="flex items-start justify-between">
            <div>
              <h3 class="text-sm font-medium text-blue-900 dark:text-blue-200 mb-1">How to use:</h3>
              <p class="text-sm text-blue-800 dark:text-blue-300">
                Type keywords with color tags: <code class="bg-blue-100 dark:bg-blue-800 px-1 rounded font-mono">[red] emergency urgent [blue] aircraft runway</code>
              </p>
            </div>
            <div class="flex flex-wrap gap-1 ml-4">
              <span class="px-2 py-1 bg-red-500 text-white rounded text-xs">red</span>
              <span class="px-2 py-1 bg-yellow-500 text-white rounded text-xs">yellow</span>
              <span class="px-2 py-1 bg-blue-500 text-white rounded text-xs">blue</span>
              <span class="px-2 py-1 bg-green-500 text-white rounded text-xs">green</span>
              <span class="px-2 py-1 bg-purple-500 text-white rounded text-xs">purple</span>
              <span class="px-2 py-1 bg-orange-500 text-white rounded text-xs">orange</span>
            </div>
          </div>
        </div>

        <!-- Editor Mode -->
        <div v-if="!previewMode" class="p-6">
          <div class="mb-4">
            <label class="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
              Keywords Editor
            </label>
            <textarea
              v-model="rawText"
              @input="debouncedSave"
              placeholder="[red] emergency urgent critical [yellow] weather visibility [blue] aircraft runway [green] clearance approved"
              rows="12"
              class="w-full px-4 py-3 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent dark:bg-gray-700 dark:text-white font-mono text-sm resize-none"
            ></textarea>
          </div>
          
          <div class="flex items-center justify-between">
            <div class="text-sm text-gray-500 dark:text-gray-400">
              <span v-if="saving" class="text-blue-600">Saving...</span>
              <span v-else-if="lastSaved" class="text-green-600">Saved at {{ lastSaved }}</span>
              <span v-else class="text-gray-400">Changes auto-save</span>
            </div>
            <button
              @click="saveKeywords"
              :disabled="saving"
              class="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors text-sm"
            >
              {{ saving ? 'Saving...' : 'Save Now' }}
            </button>
          </div>
        </div>

        <!-- Preview Mode -->
        <div v-else class="p-6">
          <div v-if="Object.keys(keywordsByCategory).length === 0" class="text-center py-12 text-gray-500 dark:text-gray-400">
            <div class="mb-2">No keywords parsed yet</div>
            <button
              @click="togglePreview"
              class="text-blue-600 hover:text-blue-700 text-sm"
            >
              Switch to editor to add keywords
            </button>
          </div>
          
          <div v-else class="space-y-6">
            <div v-for="(keywords, categoryName) in keywordsByCategory" :key="categoryName" class="border border-gray-200 dark:border-gray-600 rounded-lg p-4">
              <div class="flex items-center gap-2 mb-3">
                <div
                  class="w-3 h-3 rounded-full"
                  :style="{ backgroundColor: categories[categoryName] }"
                ></div>
                <h3 class="font-medium text-gray-900 dark:text-white capitalize">
                  {{ categoryName }}
                </h3>
                <span class="text-sm text-gray-500 dark:text-gray-400">
                  ({{ keywords.length }} keywords)
                </span>
              </div>
              
              <div class="flex flex-wrap gap-2">
                <span
                  v-for="keyword in keywords"
                  :key="keyword"
                  class="px-3 py-1 text-sm rounded-full border-2"
                  :style="{
                    borderColor: categories[categoryName],
                    color: categories[categoryName],
                    backgroundColor: categories[categoryName] + '10'
                  }"
                >
                  {{ keyword }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Quick Actions -->
      <div v-if="!previewMode" class="mt-6 bg-gray-50 dark:bg-gray-800/50 rounded-lg p-4">
        <h4 class="text-sm font-medium text-gray-900 dark:text-white mb-3">Quick Templates</h4>
        <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
          <button
            @click="addTemplate('emergency')"
            class="text-left p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            <div class="font-medium text-sm text-gray-900 dark:text-white">Emergency Template</div>
            <div class="text-xs text-gray-500 dark:text-gray-400 mt-1">Add common emergency keywords</div>
          </button>
          <button
            @click="addTemplate('aviation')"
            class="text-left p-3 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded-lg hover:bg-gray-50 dark:hover:bg-gray-700 transition-colors"
          >
            <div class="font-medium text-sm text-gray-900 dark:text-white">Aviation Template</div>
            <div class="text-xs text-gray-500 dark:text-gray-400 mt-1">Add aviation-specific keywords</div>
          </button>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useNERKeywordManager } from '~/composables/useNERKeywordManager'

const {
  // State
  categories,
  keywordsByCategory,
  stats,
  saving,
  lastSaved,
  rawText,
  previewMode,
  
  // Computed
  totalKeywords,
  activeCategories,
  showSaveStatus,
  
  // Methods
  loadData,
  saveKeywords,
  debouncedSave,
  exportKeywords,
  importKeywords,
  togglePreview
} = useNERKeywordManager()

onMounted(() => {
  loadData()
})

const addTemplate = (type: string) => {
  const templates = {
    emergency: '\n[red] emergency urgent critical mayday distress help [yellow] caution warning alert',
    aviation: '\n[blue] aircraft runway takeoff landing approach [green] clearance approved roger [purple] altitude heading speed'
  }
  
  if (templates[type as keyof typeof templates]) {
    rawText.value += templates[type as keyof typeof templates]
    debouncedSave()
  }
}
</script>