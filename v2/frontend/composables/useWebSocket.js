import { ref } from "vue";

export const useWebSocket = () => {
  const ws = ref(null);
  const isConnected = ref(false);
  const segments = ref([]);
  const error = ref(null);
  let reconnectTimeout = null;

  const connect = () => {
    if (ws.value?.readyState === WebSocket.OPEN) {
      console.log("WebSocket already connected");
      return;
    }

    console.log("Attempting WebSocket connection...");
    ws.value = new WebSocket("ws://localhost:8000/ws/diarize");

    ws.value.onopen = () => {
      console.log("WebSocket connected successfully");
      isConnected.value = true;
      error.value = null;
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
      const data = JSON.parse(event.data);
      segments.value = data.segments.map((segment) => ({
        ...segment,
        speaker: `${segment.speaker}`,
        startFormatted: formatTime(segment.start),
        endFormatted: formatTime(segment.end),
        text: `[Speaker ${segment.speaker} audio]`,
      }));
      console.log(segments.value);
    };
  };

  const sendAudioChunk = (chunk) => {
    if (!ws.value || ws.value.readyState !== WebSocket.OPEN) {
      console.log("Cannot send: WebSocket not open");
      return;
    }

    ws.value.send(
      JSON.stringify({
        audio: chunk,
      }),
    );
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