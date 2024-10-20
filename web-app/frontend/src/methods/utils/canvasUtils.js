// src/utils/canvasUtils.js

/**
 * Draws the waveform line on the given canvas context.
 * @param {CanvasRenderingContext2D} canvasCtx - The canvas 2D context.
 * @param {number} canvasWidth - Width of the canvas.
 * @param {number} canvasHeight - Height of the canvas.
 * @param {Uint8Array} rollingBuffer - Rolling audio buffer data.
 * @param {number} bufferLength - Length of each buffer slice.
 * @param {number} totalSlices - Total number of slices to display.
 * @param {number} verticalOffset - Vertical offset for waveform positioning.
 * @param {string} strokeStyle - Stroke color for the waveform line.
 * @param {number} lineWidth - Width of the waveform line.
 */
export function drawWaveformLine({
  canvasCtx,
  canvasWidth,
  canvasHeight,
  rollingBuffer,
  bufferLength,
  totalSlices,
  verticalOffset,
  strokeStyle = '#00FFCC',
  lineWidth = 2,
}) {
  canvasCtx.lineWidth = lineWidth;
  canvasCtx.strokeStyle = strokeStyle;
  canvasCtx.beginPath();

  const sliceWidth = canvasWidth / totalSlices;
  let x = 0;
  const centerY = canvasHeight / 2 - verticalOffset;

  for (let i = 0; i < rollingBuffer.length; i += bufferLength) {
    const v = rollingBuffer[i] / 128.0 - 1.0;
    const y = centerY + v * (canvasHeight / 4);

    if (i === 0) {
      canvasCtx.moveTo(x, y);
    } else {
      canvasCtx.lineTo(x, y);
    }
    x += sliceWidth;
  }
  canvasCtx.stroke();
}



/**
 * Draws the minimum and maximum lines on the canvas.
 * @param {CanvasRenderingContext2D} canvasCtx - The canvas 2D context.
 * @param {number} canvasWidth - Width of the canvas.
 * @param {number} normalizedMinValue - Normalized minimum Y value.
 * @param {number} normalizedMaxValue - Normalized maximum Y value.
 * @param {string} minLineColor - Stroke color for the min line.
 * @param {string} maxLineColor - Stroke color for the max line.
 * @param {number} lineWidth - Width of the lines.
 */
export function drawMinMaxLines({
  canvasCtx,
  canvasWidth,
  normalizedMinValue,
  normalizedMaxValue,
  minLineColor = '#21219a',
  maxLineColor = '#f83030',
  lineWidth = 1,
}) {
  // Draw max line
  canvasCtx.strokeStyle = maxLineColor;
  canvasCtx.lineWidth = lineWidth;
  canvasCtx.beginPath();
  canvasCtx.moveTo(0, normalizedMaxValue);
  canvasCtx.lineTo(canvasWidth, normalizedMaxValue);
  canvasCtx.stroke();

  // Draw min line
  canvasCtx.strokeStyle = minLineColor;
  canvasCtx.beginPath();
  canvasCtx.moveTo(0, normalizedMinValue);
  canvasCtx.lineTo(canvasWidth, normalizedMinValue);
  canvasCtx.stroke();
}

/**
 * Draws the activation threshold lines on the canvas.
 * @param {CanvasRenderingContext2D} canvasCtx - The canvas 2D context.
 * @param {number} canvasWidth - Width of the canvas.
 * @param {number} centerY - Y-coordinate for the center line.
 * @param {number} activationThresholdY - Y-offset for threshold lines.
 * @param {string} strokeStyle - Stroke color for the threshold lines.
 * @param {number} lineWidth - Width of the threshold lines.
 */
export function drawActivationThresholdLines({
  canvasCtx,
  canvasWidth,
  centerY,
  activationThresholdY,
  strokeStyle = '#919b07',
  lineWidth = 1,
}) {
  canvasCtx.strokeStyle = strokeStyle;
  canvasCtx.lineWidth = lineWidth;
  canvasCtx.beginPath();
  canvasCtx.moveTo(0, centerY - activationThresholdY);
  canvasCtx.lineTo(canvasWidth, centerY - activationThresholdY);

  canvasCtx.moveTo(0, centerY + activationThresholdY);
  canvasCtx.lineTo(canvasWidth, centerY + activationThresholdY);
  canvasCtx.stroke();
}



/**
 * Updates the rolling buffer with new audio data.
 * @param {AnalyserNode} analyser - The AnalyserNode from the Web Audio API.
 * @param {Uint8Array} dataArray - The array to store the time domain data.
 * @param {Uint8Array} rollingBuffer - The rolling buffer to update.
 * @param {number} bufferLength - Length of each buffer slice.
 */
export function updateRollingBuffer({
  analyser,
  dataArray,
  rollingBuffer,
  bufferLength,
}) {
  analyser.getByteTimeDomainData(dataArray);
  rollingBuffer.copyWithin(0, bufferLength);
  rollingBuffer.set(dataArray, rollingBuffer.length - bufferLength);
}