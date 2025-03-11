import { ref } from "vue";
import { useConfig } from "./useConfig";

export const useMinutes = () => {
    const { baseUrl } = useConfig();
    const isGeneratingMinutes = ref(false);
    const error = ref(null);
    
    const createMinutes = async () => {
        isGeneratingMinutes.value = true;
        error.value = null;
        
        try {
            const response = await fetch(`http://${baseUrl.value}/minutes`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                }
            });
            
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || 'Failed to generate minutes');
            }
            
            return true;
        } catch (err) {
            error.value = err.message || 'An error occurred while generating minutes';
            console.error('Minutes generation error:', err);
            return false;
        } finally {
            isGeneratingMinutes.value = false;
        }
    };
    
    const downloadMinutes = () => {
        const downloadUrl = `http://${baseUrl.value}/download/minutes`;
        
        const link = document.createElement("a");
        link.href = downloadUrl;
        link.download = "meeting_minutes.md";
        
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
    };
    
    const createAndDownloadMinutes = async () => {
        const success = await createMinutes();
        if (success) {
            downloadMinutes();
        }
    };
    
    return {
        isGeneratingMinutes,
        createMinutes,
        downloadMinutes,
        createAndDownloadMinutes
    };
};