export function resizeCanvas(canvas, canvasCtx) {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = 600 * dpr;
  canvas.height = 500 * dpr;
  canvas.style.width = '600px';
  canvas.style.height = '500px';
  canvasCtx.scale(dpr, dpr);
}
