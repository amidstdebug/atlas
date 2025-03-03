import { ref } from "vue";

export const useWebSocket = () => {
    const ws = ref(null);
    const isConnected = ref(false);
    const segments = ref([]);
    const error = ref(null);
    let reconnectTimeout = null;
    let sampleRate = 44100;

    // Add queue for audio chunks and processing state
    const audioQueue = [];
    let isProcessing = false;

    const connect = () => {
        if (ws.value?.readyState === WebSocket.OPEN) {
            console.log("WebSocket already connected");
            return;
        }

        console.log("Attempting WebSocket connection...");
        ws.value = new WebSocket("ws://localhost:8000/ws/diarize");

        // Essential for efficient binary data
        ws.value.binaryType = "arraybuffer";

        ws.value.onopen = () => {
            console.log("WebSocket connected successfully");
            isConnected.value = true;
            error.value = null;

            // Send initial configuration once
            ws.value.send(
                JSON.stringify({
                    type: "config",
                    sampleRate: sampleRate,
                    channels: 1,
                    format: "float32",
                }),
            );
        };

        ws.value.onclose = (event) => {
            console.log("WebSocket closed:", event.code, event.reason);
            isConnected.value = false;
            ws.value = null;

            // Reset processing state and clear queue when connection closes
            isProcessing = false;
            audioQueue.length = 0;
        };

        ws.value.onerror = (e) => {
            console.error("WebSocket error:", e);
            error.value = "WebSocket error occurred";

            // Reset processing state on error
            isProcessing = false;
        };

        ws.value.onmessage = (event) => {
            // Handle text data (JSON responses)
            console.log(event.data);
            if (typeof event.data === "string") {
                try {
                    const data = JSON.parse(event.data);
                    if (data.segments) {
                        segments.value = data.segments.map((segment) => ({
                            ...segment,
                            speaker: `${segment.speaker}`,
                            startFormatted: formatTime(segment.start),
                            endFormatted: formatTime(segment.end)
                        }));
                    }

                    // Process the next chunk in the queue after receiving a response
                    isProcessing = false;
                    processNextChunk();
                } catch (e) {
                    console.error("Error parsing WebSocket message:", e);
                    isProcessing = false;
                }
            } else {
                // For any binary responses (if any)
                isProcessing = false;
                processNextChunk();
            }
        };
    };

    const sendAudioChunk = (chunk, rate = 44100) => {
        if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
            console.log("Cannot send: WebSocket not open");
            return;
        }

        // Update sample rate if it changed
        if (rate !== sampleRate) {
            sampleRate = rate;
            ws.value.send(
                JSON.stringify({
                    type: "config",
                    sampleRate: sampleRate,
                    channels: 1,
                    format: "float32",
                }),
            );
        }

        // Add the chunk to the queue instead of sending immediately
        if (chunk.byteLength > 0) {
            audioQueue.push(chunk);
            console.log(`Added chunk to queue (${audioQueue.length} chunks waiting)`);

            // Try to process the queue if we're not already processing
            if (!isProcessing) {
                processNextChunk();
            }
        }
    };

    // New function to process the next chunk in the queue
    const processNextChunk = () => {
        if (audioQueue.length === 0 || isProcessing || !ws.value || ws.value.readyState !== WebSocket.OPEN) {
            return;
        }

        isProcessing = true;
        const nextChunk = audioQueue.shift();
        console.log(`Processing chunk (${audioQueue.length} chunks left in queue)`);

        // Send raw binary data directly
        console.log(nextChunk);
        ws.value.send(nextChunk);
    };

    const disconnect = () => {
        console.log("Disconnecting WebSocket...");
        if (reconnectTimeout) {
            clearTimeout(reconnectTimeout);
            reconnectTimeout = null;
        }

        if (ws.value) {
            ws.value.close();
            ws.value = null;
        }

        isConnected.value = false;
        error.value = null;

        // Clear the queue and reset processing state
        audioQueue.length = 0;
        isProcessing = false;
    };

    const formatTime = (seconds) => {
        const mins = Math.floor(seconds / 60);
        const secs = Math.floor(seconds % 60);
        return `${mins.toString().padStart(2, "0")}:${secs.toString().padStart(2, "0")}`;
    };

    return {
        isConnected,
        segments,
        error,
        connect,
        sendAudioChunk,
        disconnect,
    };
};
