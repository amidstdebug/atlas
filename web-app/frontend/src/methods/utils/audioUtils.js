// src/methods/utils/audioUtils.js

/**
 * Writes a string to a DataView at the specified offset.
 * @param {DataView} view - The DataView to write to.
 * @param {number} offset - The byte offset in the DataView.
 * @param {string} string - The string to write.
 */
export function writeString(view, offset, string) {
  for (let i = 0; i < string.length; i++) {
    view.setUint8(offset + i, string.charCodeAt(i));
  }
}

/**
 * Encodes raw audio samples into a WAV Blob.
 * @param {Float32Array} samples - The audio samples.
 * @param {number} sampleRate - The sample rate of the audio.
 * @returns {Blob} - The WAV file as a Blob.
 */
export function encodeWAV(samples, sampleRate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);

  // RIFF chunk descriptor
  writeString(view, 0, 'RIFF');
  view.setUint32(4, 36 + samples.length * 2, true);
  writeString(view, 8, 'WAVE');

  // FMT sub-chunk
  writeString(view, 12, 'fmt ');
  view.setUint32(16, 16, true); // Subchunk1Size (16 for PCM)
  view.setUint16(20, 1, true);  // AudioFormat (1 for PCM)
  view.setUint16(22, 1, true);  // NumChannels (1 for Mono)
  view.setUint32(24, sampleRate, true); // SampleRate
  view.setUint32(28, sampleRate * 2, true); // ByteRate
  view.setUint16(32, 2, true);  // BlockAlign
  view.setUint16(34, 16, true); // BitsPerSample

  // Data sub-chunk
  writeString(view, 36, 'data');
  view.setUint32(40, samples.length * 2, true);

  // Write PCM samples
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(
      offset,
      s < 0 ? s * 0x8000 : s * 0x7FFF,
      true
    );
  }

  return new Blob([view], { type: 'audio/wav' });
}