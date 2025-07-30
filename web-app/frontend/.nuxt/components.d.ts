
import type { DefineComponent, SlotsType } from 'vue'
type IslandComponent<T extends DefineComponent> = T & DefineComponent<{}, {refresh: () => Promise<void>}, {}, {}, {}, {}, {}, {}, {}, {}, {}, {}, SlotsType<{ fallback: { error: unknown } }>>
type HydrationStrategies = {
  hydrateOnVisible?: IntersectionObserverInit | true
  hydrateOnIdle?: number | true
  hydrateOnInteraction?: keyof HTMLElementEventMap | Array<keyof HTMLElementEventMap> | true
  hydrateOnMediaQuery?: string
  hydrateAfter?: number
  hydrateWhen?: boolean
  hydrateNever?: true
}
type LazyComponent<T> = (T & DefineComponent<HydrationStrategies, {}, {}, {}, {}, {}, {}, { hydrated: () => void }>)
interface _GlobalComponents {
      'AudioSimulationPlayer': typeof import("../components/AudioSimulationPlayer.vue")['default']
    'AudioUploadPlayer': typeof import("../components/AudioUploadPlayer.vue")['default']
    'ConfigPanel': typeof import("../components/ConfigPanel.vue")['default']
    'HeaderBar': typeof import("../components/HeaderBar.vue")['default']
    'HealthCheckOverlay': typeof import("../components/HealthCheckOverlay.vue")['default']
    'HealthStatus': typeof import("../components/HealthStatus.vue")['default']
    'HealthStatusModal': typeof import("../components/HealthStatusModal.vue")['default']
    'InvestigationPanel': typeof import("../components/InvestigationPanel.vue")['default']
    'LiveIncidentPanel': typeof import("../components/LiveIncidentPanel.vue")['default']
    'Main': typeof import("../components/Main.vue")['default']
    'NERLegend': typeof import("../components/NERLegend.vue")['default']
    'NERLegendModal': typeof import("../components/NERLegendModal.vue")['default']
    'TranscriptionPanel': typeof import("../components/TranscriptionPanel.vue")['default']
    'NuxtWelcome': typeof import("../node_modules/nuxt/dist/app/components/welcome.vue")['default']
    'NuxtLayout': typeof import("../node_modules/nuxt/dist/app/components/nuxt-layout")['default']
    'NuxtErrorBoundary': typeof import("../node_modules/nuxt/dist/app/components/nuxt-error-boundary.vue")['default']
    'ClientOnly': typeof import("../node_modules/nuxt/dist/app/components/client-only")['default']
    'DevOnly': typeof import("../node_modules/nuxt/dist/app/components/dev-only")['default']
    'ServerPlaceholder': typeof import("../node_modules/nuxt/dist/app/components/server-placeholder")['default']
    'NuxtLink': typeof import("../node_modules/nuxt/dist/app/components/nuxt-link")['default']
    'NuxtLoadingIndicator': typeof import("../node_modules/nuxt/dist/app/components/nuxt-loading-indicator")['default']
    'NuxtTime': typeof import("../node_modules/nuxt/dist/app/components/nuxt-time.vue")['default']
    'NuxtRouteAnnouncer': typeof import("../node_modules/nuxt/dist/app/components/nuxt-route-announcer")['default']
    'NuxtImg': typeof import("../node_modules/nuxt/dist/app/components/nuxt-stubs")['NuxtImg']
    'NuxtPicture': typeof import("../node_modules/nuxt/dist/app/components/nuxt-stubs")['NuxtPicture']
    'Accordion': typeof import("../components/ui/accordion/index")['Accordion']
    'AccordionContent': typeof import("../components/ui/accordion/index")['AccordionContent']
    'AccordionItem': typeof import("../components/ui/accordion/index")['AccordionItem']
    'AccordionTrigger': typeof import("../components/ui/accordion/index")['AccordionTrigger']
    'Alert': typeof import("../components/ui/alert/index")['Alert']
    'AlertDescription': typeof import("../components/ui/alert/index")['AlertDescription']
    'AlertTitle': typeof import("../components/ui/alert/index")['AlertTitle']
    'Badge': typeof import("../components/ui/badge/index")['Badge']
    'Button': typeof import("../components/ui/button/index")['Button']
    'Carousel': typeof import("../components/ui/carousel/index")['Carousel']
    'CarouselContent': typeof import("../components/ui/carousel/index")['CarouselContent']
    'CarouselItem': typeof import("../components/ui/carousel/index")['CarouselItem']
    'CarouselNext': typeof import("../components/ui/carousel/index")['CarouselNext']
    'CarouselPrevious': typeof import("../components/ui/carousel/index")['CarouselPrevious']
    'CarouselApi': typeof import("../components/ui/carousel/index")['CarouselApi']
    'Card': typeof import("../components/ui/card/index")['Card']
    'CardAction': typeof import("../components/ui/card/index")['CardAction']
    'CardContent': typeof import("../components/ui/card/index")['CardContent']
    'CardDescription': typeof import("../components/ui/card/index")['CardDescription']
    'CardFooter': typeof import("../components/ui/card/index")['CardFooter']
    'CardHeader': typeof import("../components/ui/card/index")['CardHeader']
    'CardTitle': typeof import("../components/ui/card/index")['CardTitle']
    'Input': typeof import("../components/ui/input/index")['Input']
    'Dialog': typeof import("../components/ui/dialog/index")['Dialog']
    'DialogContent': typeof import("../components/ui/dialog/index")['DialogContent']
    'DialogHeader': typeof import("../components/ui/dialog/index")['DialogHeader']
    'DialogTitle': typeof import("../components/ui/dialog/index")['DialogTitle']
    'DialogTrigger': typeof import("../components/ui/dialog/index")['DialogTrigger']
    'Label': typeof import("../components/ui/label/index")['Label']
    'Progress': typeof import("../components/ui/progress/index")['Progress']
    'Switch': typeof import("../components/ui/switch/index")['Switch']
    'Textarea': typeof import("../components/ui/textarea/index")['Textarea']
    'ColorScheme': typeof import("../node_modules/@nuxtjs/color-mode/dist/runtime/component.vue3.vue")['default']
    'NuxtPage': typeof import("../node_modules/nuxt/dist/pages/runtime/page")['default']
    'NoScript': typeof import("../node_modules/nuxt/dist/head/runtime/components")['NoScript']
    'Link': typeof import("../node_modules/nuxt/dist/head/runtime/components")['Link']
    'Base': typeof import("../node_modules/nuxt/dist/head/runtime/components")['Base']
    'Title': typeof import("../node_modules/nuxt/dist/head/runtime/components")['Title']
    'Meta': typeof import("../node_modules/nuxt/dist/head/runtime/components")['Meta']
    'Style': typeof import("../node_modules/nuxt/dist/head/runtime/components")['Style']
    'Head': typeof import("../node_modules/nuxt/dist/head/runtime/components")['Head']
    'Html': typeof import("../node_modules/nuxt/dist/head/runtime/components")['Html']
    'Body': typeof import("../node_modules/nuxt/dist/head/runtime/components")['Body']
    'NuxtIsland': typeof import("../node_modules/nuxt/dist/app/components/nuxt-island")['default']
    'NuxtRouteAnnouncer': IslandComponent<typeof import("../node_modules/nuxt/dist/app/components/server-placeholder")['default']>
      'LazyAudioSimulationPlayer': LazyComponent<typeof import("../components/AudioSimulationPlayer.vue")['default']>
    'LazyAudioUploadPlayer': LazyComponent<typeof import("../components/AudioUploadPlayer.vue")['default']>
    'LazyConfigPanel': LazyComponent<typeof import("../components/ConfigPanel.vue")['default']>
    'LazyHeaderBar': LazyComponent<typeof import("../components/HeaderBar.vue")['default']>
    'LazyHealthCheckOverlay': LazyComponent<typeof import("../components/HealthCheckOverlay.vue")['default']>
    'LazyHealthStatus': LazyComponent<typeof import("../components/HealthStatus.vue")['default']>
    'LazyHealthStatusModal': LazyComponent<typeof import("../components/HealthStatusModal.vue")['default']>
    'LazyInvestigationPanel': LazyComponent<typeof import("../components/InvestigationPanel.vue")['default']>
    'LazyLiveIncidentPanel': LazyComponent<typeof import("../components/LiveIncidentPanel.vue")['default']>
    'LazyMain': LazyComponent<typeof import("../components/Main.vue")['default']>
    'LazyNERLegend': LazyComponent<typeof import("../components/NERLegend.vue")['default']>
    'LazyNERLegendModal': LazyComponent<typeof import("../components/NERLegendModal.vue")['default']>
    'LazyTranscriptionPanel': LazyComponent<typeof import("../components/TranscriptionPanel.vue")['default']>
    'LazyNuxtWelcome': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/welcome.vue")['default']>
    'LazyNuxtLayout': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-layout")['default']>
    'LazyNuxtErrorBoundary': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-error-boundary.vue")['default']>
    'LazyClientOnly': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/client-only")['default']>
    'LazyDevOnly': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/dev-only")['default']>
    'LazyServerPlaceholder': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/server-placeholder")['default']>
    'LazyNuxtLink': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-link")['default']>
    'LazyNuxtLoadingIndicator': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-loading-indicator")['default']>
    'LazyNuxtTime': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-time.vue")['default']>
    'LazyNuxtRouteAnnouncer': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-route-announcer")['default']>
    'LazyNuxtImg': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-stubs")['NuxtImg']>
    'LazyNuxtPicture': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-stubs")['NuxtPicture']>
    'LazyAccordion': LazyComponent<typeof import("../components/ui/accordion/index")['Accordion']>
    'LazyAccordionContent': LazyComponent<typeof import("../components/ui/accordion/index")['AccordionContent']>
    'LazyAccordionItem': LazyComponent<typeof import("../components/ui/accordion/index")['AccordionItem']>
    'LazyAccordionTrigger': LazyComponent<typeof import("../components/ui/accordion/index")['AccordionTrigger']>
    'LazyAlert': LazyComponent<typeof import("../components/ui/alert/index")['Alert']>
    'LazyAlertDescription': LazyComponent<typeof import("../components/ui/alert/index")['AlertDescription']>
    'LazyAlertTitle': LazyComponent<typeof import("../components/ui/alert/index")['AlertTitle']>
    'LazyBadge': LazyComponent<typeof import("../components/ui/badge/index")['Badge']>
    'LazyButton': LazyComponent<typeof import("../components/ui/button/index")['Button']>
    'LazyCarousel': LazyComponent<typeof import("../components/ui/carousel/index")['Carousel']>
    'LazyCarouselContent': LazyComponent<typeof import("../components/ui/carousel/index")['CarouselContent']>
    'LazyCarouselItem': LazyComponent<typeof import("../components/ui/carousel/index")['CarouselItem']>
    'LazyCarouselNext': LazyComponent<typeof import("../components/ui/carousel/index")['CarouselNext']>
    'LazyCarouselPrevious': LazyComponent<typeof import("../components/ui/carousel/index")['CarouselPrevious']>
    'LazyCarouselApi': LazyComponent<typeof import("../components/ui/carousel/index")['CarouselApi']>
    'LazyCard': LazyComponent<typeof import("../components/ui/card/index")['Card']>
    'LazyCardAction': LazyComponent<typeof import("../components/ui/card/index")['CardAction']>
    'LazyCardContent': LazyComponent<typeof import("../components/ui/card/index")['CardContent']>
    'LazyCardDescription': LazyComponent<typeof import("../components/ui/card/index")['CardDescription']>
    'LazyCardFooter': LazyComponent<typeof import("../components/ui/card/index")['CardFooter']>
    'LazyCardHeader': LazyComponent<typeof import("../components/ui/card/index")['CardHeader']>
    'LazyCardTitle': LazyComponent<typeof import("../components/ui/card/index")['CardTitle']>
    'LazyInput': LazyComponent<typeof import("../components/ui/input/index")['Input']>
    'LazyDialog': LazyComponent<typeof import("../components/ui/dialog/index")['Dialog']>
    'LazyDialogContent': LazyComponent<typeof import("../components/ui/dialog/index")['DialogContent']>
    'LazyDialogHeader': LazyComponent<typeof import("../components/ui/dialog/index")['DialogHeader']>
    'LazyDialogTitle': LazyComponent<typeof import("../components/ui/dialog/index")['DialogTitle']>
    'LazyDialogTrigger': LazyComponent<typeof import("../components/ui/dialog/index")['DialogTrigger']>
    'LazyLabel': LazyComponent<typeof import("../components/ui/label/index")['Label']>
    'LazyProgress': LazyComponent<typeof import("../components/ui/progress/index")['Progress']>
    'LazySwitch': LazyComponent<typeof import("../components/ui/switch/index")['Switch']>
    'LazyTextarea': LazyComponent<typeof import("../components/ui/textarea/index")['Textarea']>
    'LazyColorScheme': LazyComponent<typeof import("../node_modules/@nuxtjs/color-mode/dist/runtime/component.vue3.vue")['default']>
    'LazyNuxtPage': LazyComponent<typeof import("../node_modules/nuxt/dist/pages/runtime/page")['default']>
    'LazyNoScript': LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['NoScript']>
    'LazyLink': LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Link']>
    'LazyBase': LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Base']>
    'LazyTitle': LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Title']>
    'LazyMeta': LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Meta']>
    'LazyStyle': LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Style']>
    'LazyHead': LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Head']>
    'LazyHtml': LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Html']>
    'LazyBody': LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Body']>
    'LazyNuxtIsland': LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-island")['default']>
    'LazyNuxtRouteAnnouncer': LazyComponent<IslandComponent<typeof import("../node_modules/nuxt/dist/app/components/server-placeholder")['default']>>
}

declare module 'vue' {
  export interface GlobalComponents extends _GlobalComponents { }
}

export const AudioSimulationPlayer: typeof import("../components/AudioSimulationPlayer.vue")['default']
export const AudioUploadPlayer: typeof import("../components/AudioUploadPlayer.vue")['default']
export const ConfigPanel: typeof import("../components/ConfigPanel.vue")['default']
export const HeaderBar: typeof import("../components/HeaderBar.vue")['default']
export const HealthCheckOverlay: typeof import("../components/HealthCheckOverlay.vue")['default']
export const HealthStatus: typeof import("../components/HealthStatus.vue")['default']
export const HealthStatusModal: typeof import("../components/HealthStatusModal.vue")['default']
export const InvestigationPanel: typeof import("../components/InvestigationPanel.vue")['default']
export const LiveIncidentPanel: typeof import("../components/LiveIncidentPanel.vue")['default']
export const Main: typeof import("../components/Main.vue")['default']
export const NERLegend: typeof import("../components/NERLegend.vue")['default']
export const NERLegendModal: typeof import("../components/NERLegendModal.vue")['default']
export const TranscriptionPanel: typeof import("../components/TranscriptionPanel.vue")['default']
export const NuxtWelcome: typeof import("../node_modules/nuxt/dist/app/components/welcome.vue")['default']
export const NuxtLayout: typeof import("../node_modules/nuxt/dist/app/components/nuxt-layout")['default']
export const NuxtErrorBoundary: typeof import("../node_modules/nuxt/dist/app/components/nuxt-error-boundary.vue")['default']
export const ClientOnly: typeof import("../node_modules/nuxt/dist/app/components/client-only")['default']
export const DevOnly: typeof import("../node_modules/nuxt/dist/app/components/dev-only")['default']
export const ServerPlaceholder: typeof import("../node_modules/nuxt/dist/app/components/server-placeholder")['default']
export const NuxtLink: typeof import("../node_modules/nuxt/dist/app/components/nuxt-link")['default']
export const NuxtLoadingIndicator: typeof import("../node_modules/nuxt/dist/app/components/nuxt-loading-indicator")['default']
export const NuxtTime: typeof import("../node_modules/nuxt/dist/app/components/nuxt-time.vue")['default']
export const NuxtRouteAnnouncer: typeof import("../node_modules/nuxt/dist/app/components/nuxt-route-announcer")['default']
export const NuxtImg: typeof import("../node_modules/nuxt/dist/app/components/nuxt-stubs")['NuxtImg']
export const NuxtPicture: typeof import("../node_modules/nuxt/dist/app/components/nuxt-stubs")['NuxtPicture']
export const Accordion: typeof import("../components/ui/accordion/index")['Accordion']
export const AccordionContent: typeof import("../components/ui/accordion/index")['AccordionContent']
export const AccordionItem: typeof import("../components/ui/accordion/index")['AccordionItem']
export const AccordionTrigger: typeof import("../components/ui/accordion/index")['AccordionTrigger']
export const Alert: typeof import("../components/ui/alert/index")['Alert']
export const AlertDescription: typeof import("../components/ui/alert/index")['AlertDescription']
export const AlertTitle: typeof import("../components/ui/alert/index")['AlertTitle']
export const Badge: typeof import("../components/ui/badge/index")['Badge']
export const Button: typeof import("../components/ui/button/index")['Button']
export const Carousel: typeof import("../components/ui/carousel/index")['Carousel']
export const CarouselContent: typeof import("../components/ui/carousel/index")['CarouselContent']
export const CarouselItem: typeof import("../components/ui/carousel/index")['CarouselItem']
export const CarouselNext: typeof import("../components/ui/carousel/index")['CarouselNext']
export const CarouselPrevious: typeof import("../components/ui/carousel/index")['CarouselPrevious']
export const CarouselApi: typeof import("../components/ui/carousel/index")['CarouselApi']
export const Card: typeof import("../components/ui/card/index")['Card']
export const CardAction: typeof import("../components/ui/card/index")['CardAction']
export const CardContent: typeof import("../components/ui/card/index")['CardContent']
export const CardDescription: typeof import("../components/ui/card/index")['CardDescription']
export const CardFooter: typeof import("../components/ui/card/index")['CardFooter']
export const CardHeader: typeof import("../components/ui/card/index")['CardHeader']
export const CardTitle: typeof import("../components/ui/card/index")['CardTitle']
export const Input: typeof import("../components/ui/input/index")['Input']
export const Dialog: typeof import("../components/ui/dialog/index")['Dialog']
export const DialogContent: typeof import("../components/ui/dialog/index")['DialogContent']
export const DialogHeader: typeof import("../components/ui/dialog/index")['DialogHeader']
export const DialogTitle: typeof import("../components/ui/dialog/index")['DialogTitle']
export const DialogTrigger: typeof import("../components/ui/dialog/index")['DialogTrigger']
export const Label: typeof import("../components/ui/label/index")['Label']
export const Progress: typeof import("../components/ui/progress/index")['Progress']
export const Switch: typeof import("../components/ui/switch/index")['Switch']
export const Textarea: typeof import("../components/ui/textarea/index")['Textarea']
export const ColorScheme: typeof import("../node_modules/@nuxtjs/color-mode/dist/runtime/component.vue3.vue")['default']
export const NuxtPage: typeof import("../node_modules/nuxt/dist/pages/runtime/page")['default']
export const NoScript: typeof import("../node_modules/nuxt/dist/head/runtime/components")['NoScript']
export const Link: typeof import("../node_modules/nuxt/dist/head/runtime/components")['Link']
export const Base: typeof import("../node_modules/nuxt/dist/head/runtime/components")['Base']
export const Title: typeof import("../node_modules/nuxt/dist/head/runtime/components")['Title']
export const Meta: typeof import("../node_modules/nuxt/dist/head/runtime/components")['Meta']
export const Style: typeof import("../node_modules/nuxt/dist/head/runtime/components")['Style']
export const Head: typeof import("../node_modules/nuxt/dist/head/runtime/components")['Head']
export const Html: typeof import("../node_modules/nuxt/dist/head/runtime/components")['Html']
export const Body: typeof import("../node_modules/nuxt/dist/head/runtime/components")['Body']
export const NuxtIsland: typeof import("../node_modules/nuxt/dist/app/components/nuxt-island")['default']
export const NuxtRouteAnnouncer: IslandComponent<typeof import("../node_modules/nuxt/dist/app/components/server-placeholder")['default']>
export const LazyAudioSimulationPlayer: LazyComponent<typeof import("../components/AudioSimulationPlayer.vue")['default']>
export const LazyAudioUploadPlayer: LazyComponent<typeof import("../components/AudioUploadPlayer.vue")['default']>
export const LazyConfigPanel: LazyComponent<typeof import("../components/ConfigPanel.vue")['default']>
export const LazyHeaderBar: LazyComponent<typeof import("../components/HeaderBar.vue")['default']>
export const LazyHealthCheckOverlay: LazyComponent<typeof import("../components/HealthCheckOverlay.vue")['default']>
export const LazyHealthStatus: LazyComponent<typeof import("../components/HealthStatus.vue")['default']>
export const LazyHealthStatusModal: LazyComponent<typeof import("../components/HealthStatusModal.vue")['default']>
export const LazyInvestigationPanel: LazyComponent<typeof import("../components/InvestigationPanel.vue")['default']>
export const LazyLiveIncidentPanel: LazyComponent<typeof import("../components/LiveIncidentPanel.vue")['default']>
export const LazyMain: LazyComponent<typeof import("../components/Main.vue")['default']>
export const LazyNERLegend: LazyComponent<typeof import("../components/NERLegend.vue")['default']>
export const LazyNERLegendModal: LazyComponent<typeof import("../components/NERLegendModal.vue")['default']>
export const LazyTranscriptionPanel: LazyComponent<typeof import("../components/TranscriptionPanel.vue")['default']>
export const LazyNuxtWelcome: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/welcome.vue")['default']>
export const LazyNuxtLayout: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-layout")['default']>
export const LazyNuxtErrorBoundary: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-error-boundary.vue")['default']>
export const LazyClientOnly: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/client-only")['default']>
export const LazyDevOnly: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/dev-only")['default']>
export const LazyServerPlaceholder: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/server-placeholder")['default']>
export const LazyNuxtLink: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-link")['default']>
export const LazyNuxtLoadingIndicator: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-loading-indicator")['default']>
export const LazyNuxtTime: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-time.vue")['default']>
export const LazyNuxtRouteAnnouncer: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-route-announcer")['default']>
export const LazyNuxtImg: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-stubs")['NuxtImg']>
export const LazyNuxtPicture: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-stubs")['NuxtPicture']>
export const LazyAccordion: LazyComponent<typeof import("../components/ui/accordion/index")['Accordion']>
export const LazyAccordionContent: LazyComponent<typeof import("../components/ui/accordion/index")['AccordionContent']>
export const LazyAccordionItem: LazyComponent<typeof import("../components/ui/accordion/index")['AccordionItem']>
export const LazyAccordionTrigger: LazyComponent<typeof import("../components/ui/accordion/index")['AccordionTrigger']>
export const LazyAlert: LazyComponent<typeof import("../components/ui/alert/index")['Alert']>
export const LazyAlertDescription: LazyComponent<typeof import("../components/ui/alert/index")['AlertDescription']>
export const LazyAlertTitle: LazyComponent<typeof import("../components/ui/alert/index")['AlertTitle']>
export const LazyBadge: LazyComponent<typeof import("../components/ui/badge/index")['Badge']>
export const LazyButton: LazyComponent<typeof import("../components/ui/button/index")['Button']>
export const LazyCarousel: LazyComponent<typeof import("../components/ui/carousel/index")['Carousel']>
export const LazyCarouselContent: LazyComponent<typeof import("../components/ui/carousel/index")['CarouselContent']>
export const LazyCarouselItem: LazyComponent<typeof import("../components/ui/carousel/index")['CarouselItem']>
export const LazyCarouselNext: LazyComponent<typeof import("../components/ui/carousel/index")['CarouselNext']>
export const LazyCarouselPrevious: LazyComponent<typeof import("../components/ui/carousel/index")['CarouselPrevious']>
export const LazyCarouselApi: LazyComponent<typeof import("../components/ui/carousel/index")['CarouselApi']>
export const LazyCard: LazyComponent<typeof import("../components/ui/card/index")['Card']>
export const LazyCardAction: LazyComponent<typeof import("../components/ui/card/index")['CardAction']>
export const LazyCardContent: LazyComponent<typeof import("../components/ui/card/index")['CardContent']>
export const LazyCardDescription: LazyComponent<typeof import("../components/ui/card/index")['CardDescription']>
export const LazyCardFooter: LazyComponent<typeof import("../components/ui/card/index")['CardFooter']>
export const LazyCardHeader: LazyComponent<typeof import("../components/ui/card/index")['CardHeader']>
export const LazyCardTitle: LazyComponent<typeof import("../components/ui/card/index")['CardTitle']>
export const LazyInput: LazyComponent<typeof import("../components/ui/input/index")['Input']>
export const LazyDialog: LazyComponent<typeof import("../components/ui/dialog/index")['Dialog']>
export const LazyDialogContent: LazyComponent<typeof import("../components/ui/dialog/index")['DialogContent']>
export const LazyDialogHeader: LazyComponent<typeof import("../components/ui/dialog/index")['DialogHeader']>
export const LazyDialogTitle: LazyComponent<typeof import("../components/ui/dialog/index")['DialogTitle']>
export const LazyDialogTrigger: LazyComponent<typeof import("../components/ui/dialog/index")['DialogTrigger']>
export const LazyLabel: LazyComponent<typeof import("../components/ui/label/index")['Label']>
export const LazyProgress: LazyComponent<typeof import("../components/ui/progress/index")['Progress']>
export const LazySwitch: LazyComponent<typeof import("../components/ui/switch/index")['Switch']>
export const LazyTextarea: LazyComponent<typeof import("../components/ui/textarea/index")['Textarea']>
export const LazyColorScheme: LazyComponent<typeof import("../node_modules/@nuxtjs/color-mode/dist/runtime/component.vue3.vue")['default']>
export const LazyNuxtPage: LazyComponent<typeof import("../node_modules/nuxt/dist/pages/runtime/page")['default']>
export const LazyNoScript: LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['NoScript']>
export const LazyLink: LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Link']>
export const LazyBase: LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Base']>
export const LazyTitle: LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Title']>
export const LazyMeta: LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Meta']>
export const LazyStyle: LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Style']>
export const LazyHead: LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Head']>
export const LazyHtml: LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Html']>
export const LazyBody: LazyComponent<typeof import("../node_modules/nuxt/dist/head/runtime/components")['Body']>
export const LazyNuxtIsland: LazyComponent<typeof import("../node_modules/nuxt/dist/app/components/nuxt-island")['default']>
export const LazyNuxtRouteAnnouncer: LazyComponent<IslandComponent<typeof import("../node_modules/nuxt/dist/app/components/server-placeholder")['default']>>

export const componentNames: string[]
