import type { RecordingState } from './types';

/**
 * Parse timestamp string like "0:00:02" to seconds
 */
export const parseTimestamp = (timestamp: string | number): number => {
  if (typeof timestamp === 'number') return timestamp;
  if (!timestamp || typeof timestamp !== 'string') return 0;
  
  const parts = timestamp.split(':');
  if (parts.length === 3) {
    const hours = parseInt(parts[0]) || 0;
    const minutes = parseInt(parts[1]) || 0;
    const seconds = parseInt(parts[2]) || 0;
    return hours * 3600 + minutes * 60 + seconds;
  } else if (parts.length === 2) {
    const minutes = parseInt(parts[0]) || 0;
    const seconds = parseInt(parts[1]) || 0;
    return minutes * 60 + seconds;
  }
  return parseFloat(timestamp) || 0;
}; 