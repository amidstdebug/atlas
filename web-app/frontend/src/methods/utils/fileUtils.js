// src/methods/utils/fileUtils.js

/**
 * Saves a Blob as a file locally by triggering a download.
 * @param {Blob} blob - The Blob to save.
 * @param {string} fileName - The desired file name.
 */
export function saveBlobLocally(blob, fileName) {
  const url = URL.createObjectURL(blob);

  const a = document.createElement('a');
  a.style.display = 'none';
  a.href = url;
  a.download = fileName;

  document.body.appendChild(a);
  a.click();

  URL.revokeObjectURL(url);
  document.body.removeChild(a);
}