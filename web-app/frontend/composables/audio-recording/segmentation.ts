import type { TranscriptionSegment } from './types';
import { parseTimestamp } from './utils';

/**
 * Build an array of TranscriptionSegment objects from the ASR `lines` format.
 * Lines where `speaker === -2` are treated as silence markers that delimit
 * individual segments. This gives us more meaningful timestamps instead of
 * one long paragraph.
 *
 * @param lines - The lines array from the WebSocket data
 * @param offset - Seconds to add to every timestamp so that each recording session starts where the previous one ended
 * @param bufferText - Trailing text that is still being processed by the model
 * @param isFinalizing - True when the backend signals that it has finished processing the current audio (type === 'ready_to_stop')
 */
export const buildSegmentsFromLines = (
  lines: any[],
  offset: number,
  bufferText: string,
  isFinalizing: boolean,
  breakPoints: number[]
): { segments: TranscriptionSegment[]; newCumulativeEndTime: number } => {
  const segments: TranscriptionSegment[] = [];
  const line = lines[0] || {};
  const fullText = (line.text || '').trim();

  if (!fullText) {
    return { segments, newCumulativeEndTime: 0 };
  }

  const sessionStartTime = parseTimestamp(line.beg ?? 0) + offset;
  const sessionEndTime = parseTimestamp(line.end ?? sessionStartTime) + offset;
  const sessionDuration = sessionEndTime - sessionStartTime;

  let lastBreak = 0;

  // Create segments for each defined breakpoint
  breakPoints.forEach(breakPoint => {
    const segmentText = fullText.substring(lastBreak, breakPoint).trim();
    if (segmentText) {
      const segmentEndTime = sessionStartTime + (breakPoint / fullText.length) * sessionDuration;
      segments.push({
        text: segmentText,
        start: lastBreak === 0 ? sessionStartTime : (segments[segments.length - 1]?.end || sessionStartTime),
        end: segmentEndTime,
      });
    }
    lastBreak = breakPoint;
  });

  // Create the final "live" segment for the remaining text
  const liveText = fullText.substring(lastBreak).trim();
  if (liveText || segments.length === 0) { // Always have at least one segment
     const liveSegmentStartTime = segments.length > 0 ? (segments[segments.length - 1]?.end || sessionStartTime) : sessionStartTime;
     segments.push({
        text: liveText,
        start: liveSegmentStartTime,
        end: sessionEndTime,
        isLive: true,
     });
  }


  // Append the buffer text to the last (live) segment
  if (bufferText && !isFinalizing && segments.length > 0) {
    const lastSegment = segments[segments.length - 1];
    lastSegment.text += (lastSegment.text ? ' ' : '') + bufferText;
  }

  return { segments, newCumulativeEndTime: sessionEndTime };
};

/**
 * Break up cumulative text into smaller, natural segments
 * (Legacy function - kept for compatibility but not currently used)
 */
export const breakTextIntoSegments = (text: string, startTime: number, endTime: number): TranscriptionSegment[] => {
  if (!text || !text.trim()) return [];

  // Split on sentence endings and natural pauses
  const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0);
  if (sentences.length <= 1) {
    // If no natural breaks, split on commas or long phrases
    const phrases = text.split(/[,;]+|(?<=\w)\s+(?=\w{4,})/).filter(s => s.trim().length > 0);
    if (phrases.length <= 1) {
      return [{ text: text.trim(), start: startTime, end: endTime }];
    }
    sentences.splice(0, sentences.length, ...phrases);
  }

  const segments: TranscriptionSegment[] = [];
  const duration = endTime - startTime;
  const avgSegmentDuration = duration / sentences.length;

  sentences.forEach((sentence, index) => {
    const segmentStart = startTime + (index * avgSegmentDuration);
    const segmentEnd = index === sentences.length - 1 ? endTime : startTime + ((index + 1) * avgSegmentDuration);

    segments.push({
      text: sentence.trim(),
      start: Math.round(segmentStart * 100) / 100,
      end: Math.round(segmentEnd * 100) / 100
    });
  });

  return segments;
};

/**
 * Detect silence breaks and mark character positions
 * (Legacy function - kept for compatibility but not currently used)
 */
export const detectSilenceBreaks = (
  currentTime: number,
  fullText: string,
  lastAudioTime: number,
  lastProcessedText: string,
  silenceBreakPoints: number[]
): { detected: boolean; newLastAudioTime: number } => {
  const timeSinceLastAudio = currentTime - lastAudioTime;
  const silenceThreshold = 3; // 3 seconds of silence

  if (timeSinceLastAudio >= silenceThreshold && lastAudioTime > 0) {
    // We detected a silence break
    const currentTextLength = fullText.length;
    const lastTextLength = lastProcessedText.length;

    // Mark where the silence break occurred (at the end of last processed text)
    if (lastTextLength > 0 && !silenceBreakPoints.includes(lastTextLength)) {
      silenceBreakPoints.push(lastTextLength);
      console.log(`[Silence] 🔇 Silence break detected at character position ${lastTextLength}`);
      return { detected: true, newLastAudioTime: currentTime };
    }
  }

  return { detected: false, newLastAudioTime: currentTime };
};

/**
 * Split text into segments based on silence break points
 * (Legacy function - kept for compatibility but not currently used)
 */
export const createSegmentsFromBreaks = (fullText: string, startTime: number, endTime: number, silenceBreakPoints: number[]): TranscriptionSegment[] => {
  if (!fullText.trim()) return [];

  const segments: TranscriptionSegment[] = [];
  const duration = endTime - startTime;

  // If no break points, return single segment
  if (silenceBreakPoints.length === 0) {
    return [{
      text: fullText.trim(),
      start: startTime,
      end: endTime
    }];
  }

  // Create segments based on break points
  let segmentStart = 0;
  let timeStart = startTime;

  for (let i = 0; i < silenceBreakPoints.length; i++) {
    const breakPoint = silenceBreakPoints[i];

    if (breakPoint <= fullText.length) {
      const segmentText = fullText.substring(segmentStart, breakPoint).trim();

      if (segmentText) {
        const segmentDuration = (breakPoint - segmentStart) / fullText.length * duration;
        const segmentEnd = timeStart + segmentDuration;

        segments.push({
          text: segmentText,
          start: Math.round(timeStart * 100) / 100,
          end: Math.round(segmentEnd * 100) / 100
        });

        timeStart = segmentEnd;
      }
      segmentStart = breakPoint;
    }
  }

  // Add final segment if there's remaining text
  if (segmentStart < fullText.length) {
    const finalText = fullText.substring(segmentStart).trim();
    if (finalText) {
      segments.push({
        text: finalText,
        start: Math.round(timeStart * 100) / 100,
        end: endTime
      });
    }
  }

  return segments;
};