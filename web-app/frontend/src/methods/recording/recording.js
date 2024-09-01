
export function setupAudioContext(drawWaveform) {
  const audioContext = new (window.AudioContext || window.webkitAudioContext)();
  const analyser = audioContext.createAnalyser();
  analyser.fftSize = 2048;

  navigator.mediaDevices.getUserMedia({ audio: true })
    .then(stream => {
      const source = audioContext.createMediaStreamSource(stream);
      source.connect(analyser);

      drawWaveform(); // Start drawing the waveform once the audio context is set up
    })
    .catch(err => {
      console.error('Error accessing audio stream:', err);
    });

  return { audioContext, analyser };
}

