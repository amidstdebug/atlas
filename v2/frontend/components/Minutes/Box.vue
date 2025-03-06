<template>
    <div class="flex flex-col h-full">
        <div class="flex justify-between items-center mb-4">
            <h2 class="text-lg font-semibold">Meeting Minutes</h2>
            <div class="text-xs text-gray-400">{{ currentStatus }}</div>
        </div>

        <div v-if="minutesError" class="text-red-500 text-sm mb-2">{{ minutesError }}</div>

        <!-- Loading state -->
        <div v-if="isMinutesLoading && minutesSections.length === 0" class="flex flex-col items-center justify-center py-8">
            <div class="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500 mb-2"></div>
            <div class="text-sm text-gray-400">Generating minutes...</div>
        </div>

        <!-- Minutes sections -->
        <div v-else class="overflow-y-auto max-h-96 pr-2 space-y-4">
            <div v-if="minutesSections.length === 0" class="text-center text-gray-400 py-8">No minutes available yet. Keep talking to generate content.</div>

            <div v-for="section in minutesSections" :key="section.id" class="border border-stone-800 rounded-lg p-4 bg-stone-900">
                <div class="flex justify-between items-start mb-2">
                    <h3 class="font-medium">{{ section.title }}</h3>
                    <span class="text-xs text-gray-400"> {{ formatTime(section.start) }} - {{ formatTime(section.end) }} </span>
                </div>

                <div class="text-xs text-gray-400 mb-2"><span class="font-medium">Participants:</span> {{ section.speakers.join(", ") }}</div>

                <p class="text-sm text-gray-300 whitespace-pre-wrap">{{ section.description }}</p>
            </div>
        </div>
    </div>
</template>

<script setup>
import { useMinutes } from "~/composables/useMinutes";

const { isMinutesLoading, error: minutesError, minutesSections, currentStatus, formatTime } = useMinutes();
</script>
