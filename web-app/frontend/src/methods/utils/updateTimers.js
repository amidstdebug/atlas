// src/methods/waveform/updateTimers.js

export function updateTimers(isRecording, recordingStartTime, recordingTimeDisplay, delayStartTime, delayDuration, delayTimeDisplay, maxReactivations, reactivationCount, reactivationsLeftDisplay) {
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
    reactivationsLeftDisplay.textContent = `Re-activations Left: ${Math.max(0, maxReactivations - reactivationCount)}`;
}
