<script setup lang="ts">
import { MessageSquare } from 'lucide-vue-next'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'

interface Props {
  transcriptionSegments: any[]
  aggregatedTranscription: string
}

const props = defineProps<Props>()


// Investigation composable
const {
  state: investigationState,
  messages,
  isInvestigating,
  askQuestion,
  clearMessages
} = useInvestigation()

// Investigation form
const investigationQuestion = ref('')

async function handleInvestigationSubmit() {
  if (!investigationQuestion.value.trim()) return

  await askQuestion(
    investigationQuestion.value,
    props.aggregatedTranscription
  )

  investigationQuestion.value = ''
}

function formatSummaryContent(content: string): string {
  return content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/\*(.*?)\*/g, '<em>$1</em>')
    .replace(/\n/g, '<br>')
}
</script>

<template>
  <Card class="h-full flex flex-col border-0 shadow-none bg-background">
    <CardHeader class="pb-2 border-b border-border">
      <div class="flex items-center justify-between">
        <div class="flex items-center space-x-3">
          <div class="p-2 rounded-lg bg-purple-100 dark:bg-purple-900/30">
            <MessageSquare class="h-5 w-5 text-purple-600 dark:text-purple-400" />
          </div>
          <div>
            <CardTitle class="text-lg">Investigation</CardTitle>
            <p class="text-sm text-muted-foreground">AI-powered investigation</p>
          </div>
        </div>
      </div>
    </CardHeader>

    <CardContent class="flex-1 flex flex-col p-4 space-y-4 overflow-y-auto">
      <!-- Chat Messages -->
      <div class="flex-1 overflow-y-auto space-y-4">
        <div v-if="messages.length === 0" class="text-center text-muted-foreground text-sm py-8">
          Ask questions about the transcription data to investigate specific details.
        </div>

        <div
          v-for="(message, index) in messages"
          :key="index"
          :class="[
            'p-3 rounded-lg',
            message.role === 'user'
              ? 'bg-purple-50 dark:bg-purple-900/30 ml-8'
              : 'bg-muted/50 mr-8'
          ]"
        >
          <div class="flex items-start space-x-2">
            <div :class="[
              'w-6 h-6 rounded-full flex items-center justify-center text-xs font-medium',
              message.role === 'user'
                ? 'bg-purple-200 dark:bg-purple-800 text-purple-800 dark:text-purple-200'
                : 'bg-muted text-muted-foreground'
            ]">
              {{ message.role === 'user' ? 'U' : 'AI' }}
            </div>
            <div class="flex-1">
              <div v-html="formatSummaryContent(message.content)" class="prose prose-sm max-w-none dark:prose-invert"></div>
              <div v-if="message.relevantSegments && message.relevantSegments.length > 0" class="mt-2">
                <p class="text-xs text-muted-foreground mb-1">Relevant segments:</p>
                <div class="space-y-1">
                  <div
                    v-for="segment in message.relevantSegments.slice(0, 3)"
                    :key="segment.line_number"
                    class="text-xs bg-background/50 p-2 rounded border"
                  >
                    {{ segment.content }}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Question Input -->
      <div class="border-t pt-4">
        <div class="flex space-x-2">
          <Textarea
            v-model="investigationQuestion"
            placeholder="Ask a question about the transcription..."
            class="flex-1 min-h-[60px] resize-none"
            @keydown.enter.ctrl="handleInvestigationSubmit"
          />
          <Button
            @click="handleInvestigationSubmit"
            :disabled="!investigationQuestion.trim() || isInvestigating"
            class="self-end"
          >
            <MessageSquare class="h-4 w-4" />
          </Button>
        </div>
        <p class="text-xs text-muted-foreground mt-1">Press Ctrl+Enter to send</p>
      </div>

    </CardContent>
  </Card>
</template>