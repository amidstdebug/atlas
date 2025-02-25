import { ref } from "vue";

export const useAudioProcessor = (onAudioChunk) => {
  const isRecording = ref(false);
  const audioContext = ref(null);
  const analyser = ref(null);
  const microphone = ref(null);
  const workletNode = ref(null);
  const waveformBars = ref(Array(40).fill(10));
  let animationFrameId = null;

  const float32ToBase64 = (float32Array) => {
    // Create a buffer to store the data
    const buffer = new ArrayBuffer(float32Array.length * 4);
    // Create a view on the buffer
    const view = new DataView(buffer);
    
    // Copy the Float32Array values into the buffer
    for (let i = 0; i < float32Array.length; i++) {
      view.setFloat32(i * 4, float32Array[i], true); // true for little-endian
    }
    
    // Convert to Uint8Array for base64 encoding
    const uint8Array = new Uint8Array(buffer);
    
    // Process in chunks for large arrays
    const chunkSize = 1024;
    let binary = "";
    
    for (let i = 0; i < uint8Array.length; i += chunkSize) {
      const chunk = uint8Array.slice(i, i + chunkSize);
      binary += String.fromCharCode.apply(null, chunk);
    }
    
    return btoa(binary);
  };

  const initAudio = async () => {
    try {
      if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
        throw new Error("Media devices API not supported");
      }

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          channelCount: 1,
          sampleRate: 16000,
        },
      });

      // Initialize audio context
      audioContext.value = new (window.AudioContext ||
        window.webkitAudioContext)({
        sampleRate: 16000,
      });

      // Load audio worklet
      await audioContext.value.audioWorklet.addModule(
        "/audioWorkletProcessor.js",
      );

      // Create audio worklet node
      workletNode.value = new AudioWorkletNode(
        audioContext.value,
        "audio-processor",
        {
          processorOptions: {
            sampleRate: 16000,
          },
        },
      );

      // Handle audio data from worklet
      workletNode.value.port.onmessage = (event) => {
        if (event.data.audioData) {
          const audioData = new Float32Array(event.data.audioData);
          const base64Data = float32ToBase64(audioData);
          onAudioChunk(base64Data);
        }
      };

      // Set up audio nodes
      microphone.value = audioContext.value.createMediaStreamSource(stream);
      analyser.value = audioContext.value.createAnalyser();
      analyser.value.fftSize = 128;

      // Connect the nodes
      microphone.value.connect(analyser.value);
      microphone.value.connect(workletNode.value);

      // Start updating waveform
      updateWaveform();

      return stream;
    } catch (error) {
      console.error("Error initializing audio:", error);
      throw error;
    }
  };

  const updateWaveform = () => {
    if (!analyser.value || !isRecording.value) return;

    const dataArray = new Uint8Array(analyser.value.frequencyBinCount);
    analyser.value.getByteFrequencyData(dataArray);

    waveformBars.value = Array.from(dataArray.slice(0, 40)).map(
      (value) => (value / 255) * 50 + 10,
    );

    animationFrameId = requestAnimationFrame(updateWaveform);
  };

  const startRecording = async () => {
    try {
      isRecording.value = true;
      const stream = await initAudio();
      if (stream && audioContext.value.state === "suspended") {
        await audioContext.value.resume();
      }
    } catch (error) {
      console.error("Error starting recording:", error);
      isRecording.value = false;
      waveformBars.value = Array(40).fill(10);
    }
  };

  const stopRecording = () => {
    isRecording.value = false;

    if (animationFrameId) {
      cancelAnimationFrame(animationFrameId);
      animationFrameId = null;
    }

    if (workletNode.value) {
      workletNode.value.disconnect();
      workletNode.value = null;
    }

    if (microphone.value) {
      microphone.value.disconnect();
      microphone.value = null;
    }

    if (audioContext.value) {
      audioContext.value.close();
      audioContext.value = null;
    }

    if (analyser.value) {
      analyser.value.disconnect();
      analyser.value = null;
    }

    waveformBars.value = Array(40).fill(10);
  };

  return {
    isRecording,
    waveformBars,
    startRecording,
    stopRecording,
  };
};