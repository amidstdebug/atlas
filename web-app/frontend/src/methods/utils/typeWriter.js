// src/utils/typewriter.js

/**
 * Typewriter effect for a single target.
 *
 * @param {String} text - The text to be typed.
 * @param {Number} typingSpeed - The speed of typing in milliseconds per character.
 * @param {Function} onUpdate - Callback function to update the UI with the current text.
 * @param {Function} [onComplete] - Callback function to be called once typing is complete.
 * @returns {Function} - A function to cancel the typing effect if needed.
 */
export function typeWriter(text, typingSpeed = 100, onUpdate, onComplete) {
  let index = 0;
  const timeouts = [];

  function typeNext() {
    if (index < text.length) {
      onUpdate(text.slice(0, index + 1));
      index++;
      const timeoutId = setTimeout(typeNext, typingSpeed);
      timeouts.push(timeoutId);
    } else {
      if (onComplete) onComplete();
    }
  }

  typeNext();

  // Return a function to cancel the typing effect
  return () => {
    timeouts.forEach((timeout) => clearTimeout(timeout));
  };
}

/**
 * Typewriter effect for multiple targets.
 *
 * @param {Array} tasks - An array of typing tasks.
 * Each task should be an object with the following properties:
 *   - text: The text to be typed.
 *   - typingSpeed: (Optional) Typing speed in milliseconds per character.
 *   - onUpdate: Callback function to update the UI with the current text.
 *   - onComplete: (Optional) Callback function once typing is complete.
 * @returns {Array} - An array of cancellation functions for each typing task.
 */
export function typeWriterMultiple(tasks) {
  const cancelFunctions = tasks.map((task) =>
    typeWriter(
      task.text,
      task.typingSpeed || 100,
      task.onUpdate,
      task.onComplete
    )
  );
  return cancelFunctions;
}