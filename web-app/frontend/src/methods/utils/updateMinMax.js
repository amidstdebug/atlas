export function updateMinMax(rollingBuffer, slicesFor4Seconds, bufferLength, canvas, verticalOffset) {
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

  return { min: normalizedMinValue, max: normalizedMaxValue };
}
