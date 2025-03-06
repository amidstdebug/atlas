import { ref, reactive } from "vue";
import { useConfig } from "./useConfig";

export const useMinutes = () => {
    const { baseUrl } = useConfig();
    
    // State
    const isLoading = ref(false);
    const error = ref(null);
    const minutesSections = ref([]);
    const currentStatus = ref("Idle");
    const showMinutes = ref(false);
    const progressPercentage = ref(0);
    
    // EventSource reference for progress updates
    let progressEventSource = null;
    
    // Start the minutes generation and connect to progress stream
    const generateMinutes = async () => {
        try {
            isLoading.value = true;
            error.value = null;
            currentStatus.value = "Starting minutes generation...";
            progressPercentage.value = 0;
            minutesSections.value = []; // Clear existing minutes
            
            // Close existing connection if any
            if (progressEventSource) {
                progressEventSource.close();
                progressEventSource = null;
            }
            
            // Connect to the progress stream
            progressEventSource = new EventSource(`http://${baseUrl.value}/minutes/progress`);
            
            // Handle connection open
            progressEventSource.onopen = () => {
                currentStatus.value = "Connected to progress stream";
            };
            
            // Handle updates
            progressEventSource.addEventListener('update', (event) => {
                try {
                    const update = JSON.parse(event.data);
                    handleProgressUpdate(update);
                } catch (err) {
                    console.error("Error parsing progress update:", err, event.data);
                    error.value = `Error processing update: ${err.message}`;
                }
            });
            
            // Handle errors
            progressEventSource.addEventListener('error', (event) => {
                closeProgressStream();
                error.value = "Error connecting to progress stream";
                isLoading.value = false;
            });
            
            return true;
        } catch (err) {
            error.value = `Failed to connect: ${err.message}`;
            isLoading.value = false;
            return false;
        }
    };
    
    // Handle different types of progress updates
    const handleProgressUpdate = (update) => {
        try {
            console.log("Progress update:", update);
            
            switch (update.type) {
                case 'status':
                    currentStatus.value = update.message;
                    break;
                    
                case 'title_generated':
                    // A new section title has been generated
                    if (update.title) {
                        currentStatus.value = `Generated title: ${update.title}`;
                    }
                    break;
                    
                case 'section_complete':
                    // Update with complete section data
                    const section = update.section;
                    if (section) {
                        // Add new section
                        minutesSections.value.push({
                            ...section,
                            id: `${section.start}-${section.end}`,
                            isComplete: true
                        });
                        
                        // Sort sections by start time
                        minutesSections.value.sort((a, b) => a.start - b.start);
                    }
                    
                    // Update progress percentage if available
                    if (update.progress_percentage) {
                        progressPercentage.value = update.progress_percentage;
                    }
                    break;
                    
                case 'complete':
                    currentStatus.value = "Minutes generation complete";
                    isLoading.value = false;
                    progressPercentage.value = 100;
                    closeProgressStream();
                    break;
                    
                case 'error':
                    error.value = update.message || "Unknown error in minutes generation";
                    isLoading.value = false;
                    closeProgressStream();
                    break;
                    
                case 'heartbeat':
                    // Just a keep-alive, no action needed
                    break;
                    
                default:
                    console.log("Unknown update type:", update.type, update);
            }
        } catch (err) {
            console.error("Error handling progress update:", err, update);
            error.value = `Error processing update: ${err.message}`;
        }
    };
    
    // Close the progress stream
    const closeProgressStream = () => {
        if (progressEventSource) {
            progressEventSource.close();
            progressEventSource = null;
        }
    };
    
    // Fetch complete minutes (for when they're already generated)
    const fetchCompleteMinutes = async () => {
        try {
            isLoading.value = true;
            error.value = null;
            currentStatus.value = "Fetching minutes...";
            
            const response = await fetch(`http://${baseUrl.value}/minutes`);
            
            // If minutes are still being generated, start the progress stream
            if (response.status === 202) {
                const data = await response.json();
                currentStatus.value = data.message || "Minutes generation in progress...";
                // Start progress updates
                return await generateMinutes();
            }
            
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
                    currentStatus.value = "Minutes loaded successfully";
                    progressPercentage.value = 100;
                } else {
                    console.warn("Received non-array sections data:", data.sections);
                    currentStatus.value = "Error: Invalid minutes data format";
                }
                return data.minutes; // Return formatted minutes
            } else {
                throw new Error(data.message || "Failed to fetch minutes");
            }
        } catch (err) {
            error.value = err.message;
            currentStatus.value = `Error: ${err.message}`;
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
        
        // Clear any previous errors when toggling
        if (showMinutes.value) {
            error.value = null;
            currentStatus.value = "Ready to generate minutes";
            
            // Try to fetch minutes if panel is shown
            if (minutesSections.value.length === 0) {
                await fetchCompleteMinutes();
            }
        } else {
            // Close the progress stream when hiding the panel
            closeProgressStream();
        }
    };
    
    // Clean up resources when component is unmounted
    const cleanup = () => {
        closeProgressStream();
    };
    
    return {
        // State
        isLoading,
        error,
        minutesSections,
        currentStatus,
        showMinutes,
        progressPercentage,
        
        // Methods
        generateMinutes,
        fetchCompleteMinutes,
        formatTime,
        toggleMinutesPanel,
        cleanup
    };
};