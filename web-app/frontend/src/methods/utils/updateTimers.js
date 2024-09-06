// src/methods/waveform/updateTimers.js

export function updateTimers(isRecording, recordingStartTime, delayStartTime, delayDuration, maxReactivations, reactivationCount, updateCallback) {
    const currentTime = Date.now();

    // Calculate the elapsed recording time
    let recordingTime = 0;
    if (isRecording && recordingStartTime) {
        recordingTime = Math.floor((currentTime - recordingStartTime) / 1000);
    }

    // Calculate the remaining delay time
    let remainingDelayTime = 0;
    if (delayStartTime) {
        remainingDelayTime = Math.max(0, delayDuration / 1000 - Math.floor((currentTime - delayStartTime) / 1000));
    }

    // Calculate the remaining reactivations
    const reactivationsLeft = Math.max(0, maxReactivations - reactivationCount);

    // Trigger the callback to update the Vue component's data
    updateCallback(recordingTime, remainingDelayTime, reactivationsLeft);
}
