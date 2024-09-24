export function resizeCanvas(canvas, canvasCtx) {
  const dpr = window.devicePixelRatio || 1;
  canvas.width = 600 * dpr;
  canvas.height = 500 * dpr;
  canvas.style.width = '500px';
  canvas.style.height = '688px';
  canvasCtx.scale(dpr, dpr);
}
