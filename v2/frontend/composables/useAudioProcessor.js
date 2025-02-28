import { ref } from "vue";

export const useAudioProcessor = (onAudioChunk) => {
    const isRecording = ref(false);
    const audioContext = ref(null);
    const analyser = ref(null);
    const microphone = ref(null);
    const workletNode = ref(null);
    const waveformBars = ref(Array(40).fill(10));
    let animationFrameId = null;

    const initAudio = async () => {
        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                throw new Error("Media devices API not supported");
            }

            // Request high quality audio
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: 44100,
                    echoCancellation: false,
                    noiseSuppression: false,
                    autoGainControl: false,
                },
            });

            // Create audio context at high quality
            audioContext.value = new (window.AudioContext || window.webkitAudioContext)({
                sampleRate: 44100,
                latencyHint: "interactive",
            });

            console.log(`Actual sample rate: ${audioContext.value.sampleRate}`);

            // Load audio worklet
            await audioContext.value.audioWorklet.addModule("/audioWorkletProcessor.js");

            // Create audio worklet node with appropriate buffer size
            workletNode.value = new AudioWorkletNode(audioContext.value, "audio-processor", {
                outputChannelCount: [1],
                processorOptions: {
                    sampleRate: audioContext.value.sampleRate,
                },
            });

            // Handle audio data from worklet
            workletNode.value.port.onmessage = (event) => {
                if (event.data.audioData) {
                    // Make sure audio data is valid before sending
                    const audioData = event.data.audioData;
                    if (audioData && audioData.byteLength > 0) {
                        // Send the raw audio data and its sample rate
                        onAudioChunk(event.data.audioData, event.data.sampleRate);
                    } else {
                        console.warn("Received empty audio data from worklet");
                    }
                }
            };

            // Set up audio nodes
            microphone.value = audioContext.value.createMediaStreamSource(stream);
            analyser.value = audioContext.value.createAnalyser();
            analyser.value.fftSize = 128;

            // Connect the nodes in series instead of parallel
            // microphone → analyser → workletNode
            microphone.value.connect(analyser.value);
            analyser.value.connect(workletNode.value);
            // Removed the direct connection from microphone to workletNode

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

        waveformBars.value = Array.from(dataArray.slice(0, 40)).map((value) => (value / 255) * 50 + 10);

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
