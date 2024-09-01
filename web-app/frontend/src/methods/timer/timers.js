let inactiveTimer = null;
let resetTimer = null;
let delayTimer = null;

export function startInactiveTimer(delayDuration, chunkBeepDuration, chunkSentButton) {
  if (inactiveTimer) {
    return;
  }
  inactiveTimer = setTimeout(() => {
    console.log('Inactive timer triggered');
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

export function resetState(activateButton, chunkSentButton, recordingTimeDisplay, delayTimeDisplay, reactivationsLeftDisplay) {
  activateButton.classList.remove('active');
  activateButton.classList.add('inactive');
  chunkSentButton.classList.remove('red');
  chunkSentButton.classList.add('grey');
  recordingTimeDisplay.textContent = 'Recording Time: 0s';
  delayTimeDisplay.textContent = 'Delay Time Left: 0s';
  reactivationsLeftDisplay.textContent = 'Re-activations Left: 2';
}

export function updateTimers(isRecording, recordingStartTime, delayStartTime, delayDuration, recordingTimeDisplay, delayTimeDisplay, reactivationsLeftDisplay, maxReactivations, reactivationCount) {
  const currentTime = Date.now();
  if (isRecording) {
    const elapsedRecordingTime = Math.floor((currentTime - recordingStartTime) / 1000);
    recordingTimeDisplay.textContent = `Recording Time: ${elapsedRecordingTime}s`;
  }
  if (delayStartTime) {
    const remainingDelayTime = Math.max(0, delayDuration / 1000 - Math.floor((currentTime - delayStartTime) / 1000));
    delayTimeDisplay.textContent = `Delay Time Left: ${remainingDelayTime}s`;
  }
  reactivationsLeftDisplay.textContent = `Re-activations Left: ${Math.max(0, maxReactivations - reactivationCount)}`;
}
