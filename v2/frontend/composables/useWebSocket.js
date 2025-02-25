import { ref } from "vue";

export const useWebSocket = () => {
  const ws = ref(null);
  const isConnected = ref(false);
  const segments = ref([]);
  const error = ref(null);
  let reconnectTimeout = null;
  let sampleRate = 44100;

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
      ws.value.send(JSON.stringify({
        type: "config",
        sampleRate: sampleRate,
        channels: 1,
        format: "float32"
      }));
    };

    ws.value.onclose = (event) => {
      console.log("WebSocket closed:", event.code, event.reason);
      isConnected.value = false;
      ws.value = null;
    };

    ws.value.onerror = (e) => {
      console.error("WebSocket error:", e);
      error.value = "WebSocket error occurred";
    };

    ws.value.onmessage = (event) => {
      // Handle text data (JSON responses)
      if (typeof event.data === "string") {
        try {
          const data = JSON.parse(event.data);
          if (data.segments) {
            segments.value = data.segments.map((segment) => ({
              ...segment,
              speaker: `${segment.speaker}`,
              startFormatted: formatTime(segment.start),
              endFormatted: formatTime(segment.end),
              text: `[Speaker ${segment.speaker} audio]`,
            }));
            console.log(segments.value);
          }
        } catch (e) {
          console.error("Error parsing WebSocket message:", e);
        }
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
      ws.value.send(JSON.stringify({
        type: "config",
        sampleRate: sampleRate,
        channels: 1,
        format: "float32"
      }));
    }

    // Send raw binary data directly
    ws.value.send(chunk);
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