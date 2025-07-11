import { useAuthStore } from '@/stores/auth';
import type { RecordingState } from './types';

export interface WebSocketHandlers {
  onProcessTranscriptionData: (data: any, isFinalizing: boolean) => void;
  onStateUpdate: (updates: Partial<RecordingState>) => void;
  onStopRecording: () => void;
}

/**
 * Initialize WebSocket connection for live transcription
 */
export const setupWebSocket = (
  handlers: WebSocketHandlers,
  variables: {
    userClosing: boolean;
    lastReceivedData: any;
    websocket: WebSocket | null;
  }
): Promise<WebSocket> => {
  return new Promise((resolve, reject) => {
    try {
      const baseUrl = process.env.NODE_ENV === 'development' ? 'ws://localhost:5002' : 'wss://your-domain.com';

      // Get JWT token from auth store
      const authStore = useAuthStore();
      const token = authStore.token;
      const url = token ?
        `${baseUrl}/ws/live-transcribe?token=${encodeURIComponent(token)}` :
        `${baseUrl}/ws/live-transcribe`;

      console.log('[WebSocket] Attempting to connect to:', url);
      const websocket = new WebSocket(url);

      // Set up connection timeout
      const connectionTimeout = setTimeout(() => {
        if (websocket.readyState === WebSocket.CONNECTING) {
          console.error('[WebSocket] ❌ Connection timeout');
          websocket.close();
          const timeoutMessage = process.env.NODE_ENV === 'development' 
            ? 'Connection timeout. Please ensure the backend server is running.'
            : 'Connection timeout. Please check your internet connection.';
          handlers.onStateUpdate({ 
            error: timeoutMessage,
            isRecording: false,
            isTranscribing: false,
            waitingForStop: false
          });
          reject(new Error(timeoutMessage));
        }
      }, 10000); // 10 second timeout
      
      websocket.onopen = () => {
        console.log('[WebSocket] ✅ Connected to server successfully');
        clearTimeout(connectionTimeout); // Clear timeout on successful connection
        handlers.onStateUpdate({ error: null });
        resolve(websocket);
      };

      websocket.onclose = (event) => {
        console.log('[WebSocket] Connection closed. Code:', event.code, 'Reason:', event.reason, 'UserClosing:', variables.userClosing);
        if (variables.userClosing) {
          console.log('[WebSocket] Processing finalized or connection closed');
          handlers.onStateUpdate({ error: 'Processing finalized or connection closed.' });
          if (variables.lastReceivedData) {
            console.log('[WebSocket] Processing final transcription data:', variables.lastReceivedData);
            handlers.onProcessTranscriptionData(variables.lastReceivedData, true);
          }
        } else {
          console.error('[WebSocket] ❌ Disconnected from the WebSocket server unexpectedly');
          handlers.onStateUpdate({ error: 'Disconnected from the WebSocket server.' });
          handlers.onStopRecording();
        }
        
        handlers.onStateUpdate({ 
          isRecording: false, 
          waitingForStop: false 
        });

        // Re-enable recording after processing is complete
        if (handlers.onStateUpdate) {
          setTimeout(() => {
            handlers.onStateUpdate({ error: null });
          }, 1000);
        }
      };

      websocket.onerror = (error) => {
        console.error('[WebSocket] ❌ Error connecting to WebSocket:', error);
        clearTimeout(connectionTimeout); // Clear timeout on error
        let errorMessage = 'Failed to connect to transcription service.';
        
        // Provide specific error messages based on common scenarios
        if (process.env.NODE_ENV === 'development') {
          errorMessage += ' Please ensure the backend server is running on localhost:5002.';
        } else {
          errorMessage += ' Please check your internet connection and try again.';
        }
        
        handlers.onStateUpdate({ 
          error: errorMessage,
          isRecording: false,
          isTranscribing: false,
          waitingForStop: false
        });
        reject(new Error(errorMessage));
      };

      // Handle messages from server
      websocket.onmessage = (event) => {
        console.log('[WebSocket] 📥 Received message, size:', event.data.length);
        let data;
        try {
          data = JSON.parse(event.data);
          console.log('[WebSocket] 📄 Parsed message data:', data);
        } catch (parseError) {
          console.error('[WebSocket] ❌ Failed to parse message:', parseError, 'Raw data:', event.data);
          return;
        }

        // Check for status messages
        if (data.type === 'ready_to_stop') {
          console.log('[WebSocket] 🏁 Ready to stop received, finalizing display and closing WebSocket');
          handlers.onStateUpdate({ waitingForStop: false });

          if (variables.lastReceivedData) {
            console.log('[WebSocket] Processing final data before close:', variables.lastReceivedData);
            handlers.onProcessTranscriptionData(variables.lastReceivedData, true);
          }
          handlers.onStateUpdate({ error: 'Finished processing audio! Ready to record again.' });
          console.log('[WebSocket] ✅ Transcription complete, ready for next recording');

          websocket.close();
          return;
        }

        variables.lastReceivedData = data;
        handlers.onProcessTranscriptionData(data, false);
      };
      
    } catch (error) {
      console.error('[WebSocket] Failed to create WebSocket:', error);
      handlers.onStateUpdate({ error: 'Invalid WebSocket URL. Please check and try again.' });
      reject(error);
    }
  });
}; 