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
      <div id="reactivationsLeft" class="timer text-color">Re-activations Left: 2</div>
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
import {resizeCanvas} from '@/methods/waveform/setupCanvas'
import {setupAudioContext} from "@/methods/recording/recording";
import {updateMinMax} from '@/methods/utils/updateMinMax';
import {updateTimers} from '@/methods/utils/updateTimers';

export default {
  mounted() {
    const canvas = document.getElementById('waveform');
    const canvasCtx = canvas.getContext('2d');
    const activateButton = document.getElementById('activateButton');
    const chunkSentButton = document.getElementById('chunkSentButton');
    const recordingTimeDisplay = document.getElementById('recordingTime');
    const delayTimeDisplay = document.getElementById('delayTime');
    const reactivationsLeftDisplay = document.getElementById('reactivationsLeft');
    const {analyser} = setupAudioContext(drawWaveform);
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    const fps = 60;
    const totalSlices = 20 * fps;
    const rollingBuffer = new Float32Array(totalSlices * bufferLength).fill(128);
    const slicesFor4Seconds = 4 * fps;
    const thresholdPercentage = 0.05;
    const activationThreshold = 3 * fps;
    const verticalOffset = 60;
    const forceSendDuration = 7000;

    let inactiveTimer = null;
    let resetTimer = null;
    let delayTimer = null;
    let reactivationCount = 0;
    let maxReactivations = 2;
    let delayDuration = 1000;
    let chunkBeepDuration = 250;
    let isRecording = false;
    let recordingStartTime = null;
    let delayStartTime = null;
    let conditionCounter = 0;
    let chunkSent = false;
    let chunkNumber = 1;
    let isActive = false;
    let forceSendTimer = null;

    let mediaRecorder;
    let recordedChunks = [];

    resizeCanvas(canvas, canvasCtx);

    async function setupMediaRecorder() {
      const stream = await navigator.mediaDevices.getUserMedia({audio: true});
      mediaRecorder = new MediaRecorder(stream);

      mediaRecorder.ondataavailable = event => {
        if (event.data.size > 0) {
          recordedChunks.push(event.data);
          // console.log('Data available:', event.data);
        } else {
          console.log('No data available:', event);
        }
      };


      // mediaRecorder.onstop = () => {
      //   sendChunkToConsole();
      // };
    }

    function sendChunkToConsole() {
      if (recordedChunks.length) {
        const blob = new Blob(recordedChunks, {type: 'audio/webm'});
        console.log('Chunk', chunkNumber, 'sent:', blob);
        recordedChunks = [];  // Clear the array for the next chunk
      }
      chunkNumber++
    }

    function drawWaveform() {
      requestAnimationFrame(drawWaveform);

      updateTimers(
          isRecording,
          recordingStartTime,
          recordingTimeDisplay,
          delayStartTime,
          delayDuration,
          delayTimeDisplay,
          maxReactivations,
          reactivationCount,
          reactivationsLeftDisplay
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
    }

    function drawMinMaxLines() {
      const {min: normalizedMinValue, max: normalizedMaxValue} = updateMinMax(
          rollingBuffer,
          bufferLength,
          slicesFor4Seconds,
          canvas,
          verticalOffset
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
      const centerY = (canvas.height / 2) - verticalOffset;
      const activationThresholdY = canvas.height * (thresholdPercentage / 2);
      canvasCtx.strokeStyle = '#919b07';
      canvasCtx.beginPath();
      canvasCtx.moveTo(0, centerY - activationThresholdY);
      canvasCtx.lineTo(canvas.width, centerY - activationThresholdY);
      canvasCtx.moveTo(0, centerY + activationThresholdY);
      canvasCtx.lineTo(canvas.width, centerY + activationThresholdY);
      canvasCtx.stroke();
    }

    function checkThresholdCondition() {
      const centerY = (canvas.height / 2) - verticalOffset;
      const centerThreshold = canvas.height * thresholdPercentage;
      const {min: normalizedMinValue, max: normalizedMaxValue} = updateMinMax(
          rollingBuffer,
          bufferLength,
          slicesFor4Seconds,
          canvas,
          verticalOffset
      );

      const withinThreshold =
          Math.abs(normalizedMaxValue - centerY) < centerThreshold &&
          Math.abs(normalizedMinValue - centerY) < centerThreshold;

      if (withinThreshold) {
        conditionCounter++;
        if (conditionCounter >= activationThreshold && isActive) {
          if (reactivationCount >= maxReactivations) {
            forceSendChunk('max');
          } else {
            deactivateRecording();
          }
        }
      } else {
        if (!isActive && !chunkSent) {
          activateRecording();
        }
        conditionCounter = 0;
        if (inactiveTimer) {
          clearTimeout(inactiveTimer);
          inactiveTimer = null;
        }
      }
    }

    drawWaveform();

    function activateRecording() {
      console.log('Activating');
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
      if (forceSendTimer) {
        clearTimeout(forceSendTimer);
      }
      forceSendTimer = setTimeout(() => {
        forceSendChunk('time');
      }, forceSendDuration);

      if (mediaRecorder.state === 'inactive') {
        mediaRecorder.start(); // Start recording if not already started
        // console.log('MediaRecorder started:', mediaRecorder.state);
      }
    }

    function deactivateRecording() {
      console.log('Deactivating');

      // Update the UI to reflect the inactive state
      activateButton.classList.remove('active');
      activateButton.classList.add('inactive');

      // Update flags and timers
      chunkSent = false;
      isActive = false;
      isRecording = false;
      delayStartTime = Date.now();
      reactivationCount++;
      console.log('Audio stopped | Reactivation count:', reactivationCount);

      // Clear the forceSendTimer if it is still active
      if (forceSendTimer) {
        clearTimeout(forceSendTimer);
        forceSendTimer = null;
      }

      // Start the delay timer for reactivation
      delayTimer = setTimeout(() => {
        startInactiveTimer();
      }, delayDuration);
    }


    function forceSendChunk(reason) {
      if (reason === 'max') {
        console.log('Max activations reached.');
      } else if (reason === 'time') {
        console.log('Max duration reached.');
      }

      chunkSentButton.classList.remove('grey');
      chunkSentButton.classList.add('red');

      mediaRecorder.stop(); // Stop the current recording to trigger chunk sending

      mediaRecorder.onstop = () => {
        sendChunkToConsole(); // Move logging to where the chunk is actually sent
      };

      resetState();

      console.log('Chunk', chunkNumber, 'sent due to', reason);
      chunkNumber++;

      // Clear the forceSendTimer here
      if (forceSendTimer) {
        clearTimeout(forceSendTimer);
        forceSendTimer = null;
      }

      resetTimer = setTimeout(() => {
        chunkSentButton.classList.remove('red');
        chunkSentButton.classList.add('grey');
      }, chunkBeepDuration);
    }

    function resetState() {
      activateButton.classList.remove('active');
      activateButton.classList.add('inactive');
      chunkSentButton.classList.remove('red');
      chunkSentButton.classList.add('grey');
      isRecording = false;
      isActive = false;
      reactivationCount = 0;
      recordingStartTime = null;
      delayStartTime = null;
      conditionCounter = 0;
      chunkSent = false;
      recordingTimeDisplay.textContent = 'Recording Time: 0s';
      delayTimeDisplay.textContent = 'Delay Time Left: 0s';
      reactivationsLeftDisplay.textContent = `Re-activations Left: ${maxReactivations}`;
      activateButton.disabled = false;
      chunkSentButton.disabled = false;

      if (resetTimer) {
        clearTimeout(resetTimer);
        resetTimer = null;
      }
      if (delayTimer) {
        clearTimeout(delayTimer);
        delayTimer = null;
      }
      if (inactiveTimer) {
        clearTimeout(inactiveTimer);
        inactiveTimer = null;
      }
      if (forceSendTimer) {
        clearTimeout(forceSendTimer);
        forceSendTimer = null;
      }
    }

    function startInactiveTimer() {
      if (inactiveTimer) {
        return;
      }
      inactiveTimer = setTimeout(() => {
        // Check if the MediaRecorder is recording and stop it
        if (mediaRecorder.state === 'recording') {
          // console.log('Stopping MediaRecorder');
          mediaRecorder.stop();
        } else {
          console.log('MediaRecorder is not in recording state:', mediaRecorder.state);
        }

        mediaRecorder.onstop = () => {
          sendChunkToConsole(); // Log the chunk data when it’s actually sent
        };

        // chunkNumber++;
        reactivationCount = 0;
        chunkSentButton.classList.remove('grey');
        chunkSentButton.classList.add('red');

        resetTimer = setTimeout(() => {
          chunkSentButton.classList.remove('red');
          chunkSentButton.classList.add('grey');
          resetTimer = null;
        }, chunkBeepDuration);

        inactiveTimer = null;
      }, delayDuration);
    }

    setupMediaRecorder(); // Call this after mounting to set up the recorder

    drawWaveform();
  }
};
</script>
