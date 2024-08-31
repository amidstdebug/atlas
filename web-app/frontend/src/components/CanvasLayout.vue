<template>
  <div>
    <canvas id="waveform"></canvas>
    <el-row>
      <button id="activateButton" class="statusButton inactive">Activated</button>
      <button id="chunkSentButton" class="chunkSentButton grey">Chunk Sent</button>
    </el-row>
    <el-row>
      <div id="recordingTime" class="timer text-color">Recording Time: 0s</div>
    </el-row>
    <el-row>
      <div id="delayTime" class="timer text-color">Delay Time Left: 0s</div>
    </el-row>
    <el-row>
      <div id="reactivationsLeft" class="timer text-color">Reactivations Left: 2</div>
    </el-row>
  </div>
</template>


<style scoped>
body {
  background-color: #121212;
  display: flex;
  justify-content: center;
  align-items: center;
  height: 100vh;
  margin: 0;
  flex-direction: column;
}

canvas {
  border: 1px solid #333;
}

.statusButton {
  padding: 10px 20px;
  font-size: 16px;
  border: none;
  border-radius: 5px;
  margin: 5px;
  color: white;
}

.inactive {
  background-color: #555;
}

.active {
  background-color: #4CAF50;
}

.chunkSentButton {
  padding: 10px 20px;
  font-size: 16px;
  border: none;
  border-radius: 5px;
  margin: 5px;
  background-color: #FF6347;
  color: white;
}

.grey {
  background-color: #555; /* Grey color for the initial state */
}

.red {
  background-color: #FF6347; /* Red color when activated */
}

.timer {
  color: #FFF;
  font-size: 18px;
  margin-top: 10px;
}

.text-color {
  color: black;
}

</style>


<script>
export default {
  mounted() {
    const canvas = document.getElementById('waveform');
    const canvasCtx = canvas.getContext('2d');
    const activateButton = document.getElementById('activateButton');
    const chunkSentButton = document.getElementById('chunkSentButton');
    const recordingTimeDisplay = document.getElementById('recordingTime');
    const delayTimeDisplay = document.getElementById('delayTime');
    const reactivationsLeftDisplay = document.getElementById('reactivationsLeft');

    let inactiveTimer = null;
    let resetTimer = null;
    let delayTimer = null;
    let reactivationCount = 0;
    let maxReactivations = 2; // Maximum allowed reactivations
    let delayDuration = 1000;
    let chunkBeepDuration = 250;
    let isRecording = false;
    let recordingStartTime = null;
    let delayStartTime = null;

    function resizeCanvas() {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = 1200 * dpr;
      canvas.height = 400 * dpr;
      canvas.style.width = '1200px';
      canvas.style.height = '400px';
      canvasCtx.scale(dpr, dpr);
    }

    resizeCanvas();

    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const analyser = audioContext.createAnalyser();
    analyser.fftSize = 2048;

    navigator.mediaDevices.getUserMedia({audio: true})
        .then(stream => {
          const source = audioContext.createMediaStreamSource(stream);
          source.connect(analyser);
          drawWaveform();
        })
        .catch(err => {
          console.error('Error accessing audio stream:', err);
        });

    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    const fps = 60;
    const totalSlices = 20 * fps;
    const rollingBuffer = new Float32Array(totalSlices * bufferLength).fill(128);
    const slicesFor4Seconds = 4 * fps;
    const thresholdPercentage = 0.05;
    let conditionCounter = 0;
    const activationThreshold = 3 * fps;
    let chunkSent = false;
    let chunkNumber = 1;
    let isActive = false;
    const verticalOffset = 60;

    function updateMinMax() {
      let minValue = Infinity;
      let maxValue = -Infinity;
      const startIndex = rollingBuffer.length - slicesFor4Seconds * bufferLength;
      for (let i = startIndex; i < rollingBuffer.length; i++) {
        const v = rollingBuffer[i] / 128.0 - 1.0;
        if (v < minValue) minValue = v;
        if (v > maxValue) maxValue = v;
      }
      const centerY = (canvas.height / 2) - verticalOffset;
      const normalizedMinValue = Math.min(canvas.height, Math.max(0, centerY + minValue * (canvas.height / 4)));
      const normalizedMaxValue = Math.min(canvas.height, Math.max(0, centerY + maxValue * (canvas.height / 4)));
      return {min: normalizedMinValue, max: normalizedMaxValue};
    }

    function updateTimers() {
      if (isRecording) {
        const currentTime = Date.now();
        const elapsedRecordingTime = Math.floor((currentTime - recordingStartTime) / 1000);
        recordingTimeDisplay.textContent = `Recording Time: ${elapsedRecordingTime}s`;
      }
      if (delayStartTime) {
        const currentTime = Date.now();
        const remainingDelayTime = Math.max(0, delayDuration / 1000 - Math.floor((currentTime - delayStartTime) / 1000));
        delayTimeDisplay.textContent = `Delay Time Left: ${remainingDelayTime}s`;
      }
      reactivationsLeftDisplay.textContent = `Reactivations Left: ${Math.max(0, maxReactivations - reactivationCount)}`;
    }

    function drawWaveform() {
      requestAnimationFrame(drawWaveform);
      updateTimers();

      analyser.getByteTimeDomainData(dataArray);
      rollingBuffer.set(rollingBuffer.subarray(bufferLength), 0);
      rollingBuffer.set(dataArray, rollingBuffer.length - bufferLength);

      const {min: normalizedMinValue, max: normalizedMaxValue} = updateMinMax();

      canvasCtx.clearRect(0, 0, canvas.width, canvas.height);
      canvasCtx.lineWidth = 2;
      canvasCtx.strokeStyle = '#00FFCC';
      canvasCtx.beginPath();
      const sliceWidth = canvas.width / totalSlices;
      let x = 0;
      const centerY = (canvas.height / 2) - verticalOffset;

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

      canvasCtx.strokeStyle = '#f83030';
      canvasCtx.lineWidth = 1;
      canvasCtx.beginPath();
      canvasCtx.moveTo(0, normalizedMaxValue);
      canvasCtx.lineTo(canvas.width, normalizedMaxValue);
      canvasCtx.stroke();

      canvasCtx.strokeStyle = '#21219a';
      canvasCtx.beginPath();
      canvasCtx.moveTo(0, normalizedMinValue);
      canvasCtx.lineTo(canvas.width, normalizedMinValue);
      canvasCtx.stroke();

      const activationThresholdY = canvas.height * (thresholdPercentage / 2);
      canvasCtx.strokeStyle = '#919b07';
      canvasCtx.beginPath();
      canvasCtx.moveTo(0, centerY - activationThresholdY);
      canvasCtx.lineTo(canvas.width, centerY - activationThresholdY);
      canvasCtx.moveTo(0, centerY + activationThresholdY);
      canvasCtx.lineTo(canvas.width, centerY + activationThresholdY);
      canvasCtx.stroke();

      const centerThreshold = canvas.height * thresholdPercentage;
      const withinThreshold = Math.abs(normalizedMaxValue - centerY) < centerThreshold && Math.abs(normalizedMinValue - centerY) < centerThreshold;

      if (withinThreshold) {
        conditionCounter++;
        if (conditionCounter >= activationThreshold && isActive) {
          // Check for maximum reactivations
          if (reactivationCount >= maxReactivations) {
            forceSendChunk('max');
          } else {
            activateButton.classList.remove('active');
            activateButton.classList.add('inactive');
            chunkSent = false;
            isActive = false;
            isRecording = false;
            delayStartTime = Date.now();
            reactivationCount++;
            console.log('Audio stopped | Reactivation count:', reactivationCount);

            delayTimer = setTimeout(() => {
              startInactiveTimer();
            }, delayDuration);
          }
        }
      } else {
        if (!isActive && !chunkSent) {
          activateButton.classList.add('active');
          activateButton.classList.remove('inactive');
          console.log('Recording chunk:', chunkNumber);
          chunkSent = true;
          isActive = true;
          isRecording = true;
          recordingStartTime = Date.now();
          delayStartTime = null;
          if (delayTimer) {
            clearTimeout(delayTimer);
            delayTimer = null;
          }
        }
        conditionCounter = 0;

        if (inactiveTimer) {
          clearTimeout(inactiveTimer);
          inactiveTimer = null;
        }
      }

    }

    function resetState() {
      // Reset all relevant state variables
      activateButton.classList.remove('active');
      activateButton.classList.add('inactive');
      chunkSentButton.classList.remove('red');
      chunkSentButton.classList.add('grey');
      isRecording = false;
      reactivationCount = 0;
      recordingStartTime = null;
      delayStartTime = null;
      recordingTimeDisplay.textContent = 'Recording Time: 0s';
      delayTimeDisplay.textContent = 'Delay Time Left: 0s';
      reactivationsLeftDisplay.textContent = `Reactivations Left: ${maxReactivations}`;

      // Clear any timers
      if (resetTimer) {
        clearTimeout(resetTimer);
        resetTimer = null;
      }
      if (delayTimer) {
        clearTimeout(delayTimer);
        delayTimer = null;
      }
    }

    function forceSendChunk(reason) {
      if (reason == 'max') {
        console.log('Maximum reactivations reached, forcing chunk send.');

      }
      chunkSentButton.classList.remove('grey');
      chunkSentButton.classList.add('red');

      resetState();

      console.log('Chunk forced sent');

      // Set a timer to turn the button back to grey after the beep duration
      resetTimer = setTimeout(() => {
        chunkSentButton.classList.remove('red');
        chunkSentButton.classList.add('grey');
      }, chunkBeepDuration);
    }

    function startInactiveTimer() {
      if (inactiveTimer) {
        return;
      }
      // console.log('Starting inactive timer...');
      inactiveTimer = setTimeout(() => {
        console.log('Chunk', chunkNumber, 'sent');
        chunkNumber++;
        reactivationCount = 0;
        chunkSentButton.classList.remove('grey');
        chunkSentButton.classList.add('red');

        // Set a timer to turn the button back to grey after 0.25 seconds
        resetTimer = setTimeout(() => {
          chunkSentButton.classList.remove('red');
          chunkSentButton.classList.add('grey');
          resetTimer = null;
        }, chunkBeepDuration);

        inactiveTimer = null;
      }, delayDuration);
    }

    drawWaveform();
  }
}
</script>

