<template>
  <header :style="headerStyle"
          class="flex items-center justify-between px-8"
          style="height: 100px; transition: background-color 0.5s;">
    <div class="flex items-center">
      <img :src="logoSrc" alt="Logo"
           class="h-12 w-auto transition-opacity duration-1000" />
    </div>
    <!-- Use NavigationMenu for the navigation bar -->
    <NavigationMenu>
      <NavigationMenuList>
        <NavigationMenuItem v-for="mode in modes" :key="mode">
          <NavigationMenuLink asChild>
            <Button
              variant="ghost"
              @click="changeMode(mode)"
              :class="[activeTabClass(mode), 'transition-colors duration-300 ease-in-out']">
              {{ mode === 'ATC' ? 'Air Incident Mode' : 'Meeting Minutes Mode' }}
            </Button>
          </NavigationMenuLink>
        </NavigationMenuItem>
      </NavigationMenuList>
    </NavigationMenu>
    <div></div>
  </header>
</template>

<script>
import {Button} from '@/components/ui/button'
import {
  NavigationMenu,
  NavigationMenuList,
  NavigationMenuItem,
  NavigationMenuLink
} from '@/components/ui/navigation-menu'

export default {
  name: "Header",
  components: { Button, NavigationMenu, NavigationMenuList, NavigationMenuItem, NavigationMenuLink },
  props: {
    activeMode: {
      type: String,
      required: true
    }
  },
  data() {
    return {
      modes: ['ATC', 'Meeting']
    }
  },
  computed: {
    headerStyle() {
      return {
        backgroundColor: this.activeMode === 'ATC' ? '#44576D' : '#8BA4B3'
      }
    },
    logoSrc() {
      return this.activeMode === 'ATC' ? 'logo-light.png' : 'logo-dark.png';
    }
  },
  methods: {
    changeMode(mode) {
      this.$emit('switch-mode', mode);
    },
    activeTabClass(mode) {
      return mode === this.activeMode
          ? 'text-white underline text-xl'
          : 'text-gray-300';
    }
  }
}
</script>

<style scoped>
/* Additional header-specific styles if needed */
</style>