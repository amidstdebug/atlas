<script setup lang="ts">
import { Sun, Moon, User, LogOut } from 'lucide-vue-next'
import { Button } from '@/components/ui/button'

interface Props {
  username?: string
}

const props = withDefaults(defineProps<Props>(), {
  username: 'User'
})

const emit = defineEmits<{
  logout: []
}>()

const { $colorMode } = useNuxtApp()

function handleLogout() {
  emit('logout')
}
</script>

<template>
  <header class="border-b border-border/50 bg-background/80 backdrop-blur-xl sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-6 py-4">
      <div class="flex items-center justify-between">
        <!-- Logo and Title -->
        <div class="flex items-center space-x-4">
          <div class="flex items-center space-x-3">
            <div class="h-10 flex items-center justify-center">
              <!-- light theme → dark logo | dark theme → light logo -->
              <img
                v-if="$colorMode.value === 'dark'"
                src="/ATLAS_light.png"
                alt="ATLAS logo (light)"
                class="h-10 object-contain"
              />
              <img
                v-else
                src="/ATLAS_dark.png"
                alt="ATLAS logo (dark)"
                class="h-10 object-contain"
              />
            </div>
            <div>
              <p class="text-sm text-muted-foreground">Air Incident Investigation</p>
            </div>
          </div>
        </div>

        <!-- Status and Controls -->
        <div class="flex items-center space-x-6">
          <!-- Theme Toggle -->
          <Button
            variant="ghost"
            size="icon"
            class="rounded-full h-8 w-8"
            @click="$colorMode.preference = $colorMode.value === 'dark' ? 'light' : 'dark'"
          >
            <Sun v-if="$colorMode.value === 'dark'" class="h-4 w-4" />
            <Moon v-else class="h-4 w-4" />
          </Button>

          <!-- User Menu -->
          <div class="flex items-center space-x-2">
            <div class="p-1.5 rounded-lg bg-muted/50">
              <User class="h-4 w-4 text-muted-foreground" />
            </div>
            <div class="text-sm">
              <p class="font-medium text-foreground">{{ username }}</p>
            </div>
            <Button
              variant="ghost"
              size="sm"
              class="text-muted-foreground hover:text-foreground"
              @click="handleLogout"
            >
              <LogOut class="h-3 w-3 mr-1" />
              Sign Out
            </Button>
          </div>
        </div>
      </div>
    </div>
  </header>
</template>