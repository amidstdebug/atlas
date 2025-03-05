import { ref, reactive } from "vue";
import { useConfig } from "./useConfig";

export const useMinutes = () => {
    const { baseUrl } = useConfig();
    
    // State
    const isStreaming = ref(false);
    const isLoading = ref(false);
    const error = ref(null);
    const minutesSections = ref([]);
    const currentStatus = ref("Idle");
    const showMinutes = ref(false);
    
    // EventSource reference
    let eventSource = null;
    
    // Connect to the SSE stream
    const startMinutesStream = () => {
        // Reset state
        isLoading.value = true;
        error.value = null;
        currentStatus.value = "Connecting...";
        
        try {
            // Close existing connection if any
            if (eventSource) {
                eventSource.close();
            }
            
            // Connect to the minutes stream
            eventSource = new EventSource(`http://${baseUrl.value}/minutes/stream`);
            isStreaming.value = true;
            
            // Handle connection open
            eventSource.onopen = () => {
                currentStatus.value = "Connected to minutes stream";
            };
            
            // Handle start event
            eventSource.addEventListener('start', (event) => {
                try {
                    const data = JSON.parse(event.data);
                    currentStatus.value = data.message;
                } catch (err) {
                    console.error("Error parsing start event:", err, event.data);
                    currentStatus.value = "Connected (error parsing start data)";
                }
            });
            
            // Handle updates
            eventSource.addEventListener('update', (event) => {
                try {
                    const updateText = event.data;
                    const data = JSON.parse(updateText);
                    handleUpdate(data);
                } catch (err) {
                    console.error("Error parsing update event:", err, event.data);
                    error.value = `Error processing update: ${err.message}`;
                }
            });
            
            // Handle errors
            eventSource.addEventListener('error', (event) => {
                error.value = "Error connecting to minutes stream";
                isStreaming.value = false;
                isLoading.value = false;
                if (eventSource) {
                    eventSource.close();
                    eventSource = null;
                }
            });
        } catch (err) {
            error.value = `Failed to connect: ${err.message}`;
            isStreaming.value = false;
            isLoading.value = false;
        }
    };
    
    // Handle different types of updates
    const handleUpdate = (update) => {
        try {
            switch (update.type) {
                case 'status':
                    currentStatus.value = update.message;
                    break;
                    
                case 'title':
                    // A new section is being created
                    const newSection = {
                        id: Date.now().toString(), // Temporary ID
                        title: update.title,
                        description: "",
                        speakers: [],
                        start: 0,
                        end: 0,
                        isComplete: false
                    };
                    minutesSections.value.push(newSection);
                    break;
                    
                case 'summary_chunk':
                    // Update the description of a section
                    if (minutesSections.value.length > 0) {
                        const lastSection = minutesSections.value[minutesSections.value.length - 1];
                        lastSection.description += update.chunk;
                    }
                    break;
                    
                case 'section_complete':
                    // Update with complete section data
                    const section = update.section;
                    if (section) {
                        // Find if we already have this section
                        const existingIndex = minutesSections.value.findIndex(s => 
                            s.start === section.start && s.end === section.end);
                        
                        if (existingIndex >= 0) {
                            // Update existing section
                            minutesSections.value[existingIndex] = {
                                ...minutesSections.value[existingIndex],
                                ...section,
                                isComplete: true
                            };
                        } else {
                            // Add new section
                            minutesSections.value.push({
                                ...section,
                                id: Date.now().toString(),
                                isComplete: true
                            });
                        }
                        
                        // Sort sections by start time
                        minutesSections.value.sort((a, b) => a.start - b.start);
                    }
                    break;
                    
                case 'complete':
                    currentStatus.value = "Minutes generation complete";
                    isLoading.value = false;
                    break;
                    
                case 'error':
                    error.value = update.message || "Unknown error in minutes generation";
                    isLoading.value = false;
                    break;
                    
                default:
                    console.log("Unknown update type:", update.type, update);
            }
        } catch (err) {
            console.error("Error handling update:", err, update);
            error.value = `Error processing update: ${err.message}`;
        }
    };
    
    // Stop the stream
    const stopMinutesStream = () => {
        if (eventSource) {
            eventSource.close();
            eventSource = null;
        }
        isStreaming.value = false;
        currentStatus.value = "Disconnected";
    };
    
    // Fetch complete minutes
    const fetchCompleteMinutes = async () => {
        try {
            isLoading.value = true;
            error.value = null;
            
            const response = await fetch(`http://${baseUrl.value}/minutes`);
            if (!response.ok) {
                throw new Error(`Server returned ${response.status}`);
            }
            
            const data = await response.json();
            if (data.status === "success") {
                // Replace current sections with the complete data
                if (Array.isArray(data.sections)) {
                    minutesSections.value = data.sections.map(section => ({
                        ...section,
                        id: `${section.start}-${section.end}`,
                        isComplete: true
                    }));
                } else {
                    console.warn("Received non-array sections data:", data.sections);
                }
                return data.minutes; // Return formatted minutes
            } else {
                throw new Error(data.message || "Failed to fetch minutes");
            }
        } catch (err) {
            error.value = err.message;
            return null;
        } finally {
            isLoading.value = false;
        }
    };
    
    // Format time as MM:SS
    const formatTime = (seconds) => {
        if (seconds === undefined || seconds === null) return "00:00";
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
    };
    
    // Toggle minutes panel visibility
    const toggleMinutesPanel = async () => {
        showMinutes.value = !showMinutes.value;
        
        if (showMinutes.value) {
            // If we're showing minutes for the first time, start streaming
            if (!isStreaming.value && minutesSections.value.length === 0) {
                startMinutesStream();
            }
        } else {
            // When hiding, we can optionally stop the stream to save resources
            // stopMinutesStream();
        }
    };
    
    // Reconnect the stream if there's an error
    const reconnectStream = () => {
        stopMinutesStream();
        startMinutesStream();
    };
    
    return {
        // State
        isStreaming,
        isLoading,
        error,
        minutesSections,
        currentStatus,
        showMinutes,
        
        // Methods
        startMinutesStream,
        stopMinutesStream,
        fetchCompleteMinutes,
        formatTime,
        toggleMinutesPanel,
        reconnectStream
    };
};