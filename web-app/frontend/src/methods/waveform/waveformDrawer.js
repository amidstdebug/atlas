import { resizeCanvas } from '@/methods/waveform/setupCanvas';
import { updateMinMax } from '@/methods/utils/updateMinMax';
import { updateTimers } from '@/methods/utils/updateTimers';

export function createWaveformDrawer(canvas, analyser, options) {
  const canvasCtx = canvas.getContext('2d');
  const bufferLength = analyser.frequencyBinCount;
  const dataArray = new Uint8Array(bufferLength);
  const rollingBuffer = new Float32Array(options.totalSlices * bufferLength).fill(128);

  let isRecording = false;
  let recordingStartTime = null;
  let delayStartTime = null;
  let conditionCounter = 0;
  let isActive = false;

  function drawWaveform() {
    requestAnimationFrame(drawWaveform);

    updateTimers(
      isRecording,
      recordingStartTime,
      options.recordingTimeDisplay,
      delayStartTime,
      options.delayDuration,
      options.delayTimeDisplay,
      options.maxReactivations,
      options.reactivationCount,
      options.reactivationsLeftDisplay
    );

    updateRollingBuffer();
    clearCanvas();
    drawWaveformLine();
    drawMinMaxLines();
    drawActivationThresholdLines();
    checkThresholdCondition();
  }

  function updateRollingBuffer() {
    analyser.getByteTimeDomainData(dataArray);
    rollingBuffer.set(rollingBuffer.subarray(bufferLength), 0);
    rollingBuffer.set(dataArray, rollingBuffer.length - bufferLength);
  }

  function clearCanvas() {
    canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
  }

  function drawWaveformLine() {
    canvasCtx.lineWidth = 2;
    canvasCtx.strokeStyle = '#00FFCC';
    canvasCtx.beginPath();

    const sliceWidth = canvas.width / options.totalSlices;
    let x = 0;
    const centerY = (canvas.height / 2) - options.verticalOffset;

    for (let i = 0; i < rollingBuffer.length; i += bufferLength) {
      const v = rollingBuffer[i] / 128.0 - 1.0;
      const y = centerY + v * (canvas.height / 4);
      if (i === 0) {
        canvasCtx.moveTo(x, y);
      } else {
        canvasCtx.lineTo(x, y);
      }
      x += sliceWidth;
    }
    canvasCtx.stroke();
  }

  function drawMinMaxLines() {
    const { min: normalizedMinValue, max: normalizedMaxValue } = updateMinMax(
      rollingBuffer,
      bufferLength,
      options.slicesFor4Seconds,
      canvas,
      options.verticalOffset
    );

    // Draw max value line
    canvasCtx.strokeStyle = '#f83030';
    canvasCtx.lineWidth = 1;
    canvasCtx.beginPath();
    canvasCtx.moveTo(0, normalizedMaxValue);
    canvasCtx.lineTo(canvas.width, normalizedMaxValue);
    canvasCtx.stroke();

    // Draw min value line
    canvasCtx.strokeStyle = '#21219a';
    canvasCtx.beginPath();
    canvasCtx.moveTo(0, normalizedMinValue);
    canvasCtx.lineTo(canvas.width, normalizedMinValue);
    canvasCtx.stroke();
  }

  function drawActivationThresholdLines() {
    const centerY = (canvas.height / 2) - options.verticalOffset;
    const activationThresholdY = canvas.height * (options.thresholdPercentage / 2);
    canvasCtx.strokeStyle = '#919b07';
    canvasCtx.beginPath();
    canvasCtx.moveTo(0, centerY - activationThresholdY);
    canvasCtx.lineTo(canvas.width, centerY - activationThresholdY);
    canvasCtx.moveTo(0, centerY + activationThresholdY);
    canvasCtx.lineTo(canvas.width, centerY + activationThresholdY);
    canvasCtx.stroke();
  }

  function checkThresholdCondition() {
    const centerY = (canvas.height / 2) - options.verticalOffset;
    const centerThreshold = canvas.height * options.thresholdPercentage;
    const { min: normalizedMinValue, max: normalizedMaxValue } = updateMinMax(
      rollingBuffer,
      bufferLength,
      options.slicesFor4Seconds,
      canvas,
      options.verticalOffset
    );

    const withinThreshold =
      Math.abs(normalizedMaxValue - centerY) < centerThreshold &&
      Math.abs(normalizedMinValue - centerY) < centerThreshold;

    if (withinThreshold) {
      conditionCounter++;
      if (conditionCounter >= options.activationThreshold && isActive) {
        options.onDeactivate();
      }
    } else {
      if (!isActive && !options.chunkSent) {
        options.onActivate();
      }
      conditionCounter = 0;
    }
  }

  function setIsRecording(value) {
    isRecording = value;
  }

  function setRecordingStartTime(value) {
    recordingStartTime = value;
  }

  function setDelayStartTime(value) {
    delayStartTime = value;
  }

  function setIsActive(value) {
    isActive = value;
  }

  resizeCanvas(canvas, canvasCtx);

  return {
    drawWaveform,
    setIsRecording,
    setRecordingStartTime,
    setDelayStartTime,
    setIsActive
  };
}