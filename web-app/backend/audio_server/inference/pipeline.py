import os
import math
import tempfile
import logging

# For audio splitting, install pydub: pip install pydub
from pydub import AudioSegment

logging.basicConfig(level=logging.INFO)

class InferencePipeline:
    """
    Modified pipeline that:
      1. Splits large audio into smaller chunks to avoid OOM during Transcription/Align
      2. Transcribes each chunk (via CanaryTranscriber), force-aligns,
      3. Merges chunk alignments
      4. Finally, passes the *full audio* to the Diarizer so that speaker labels
         are consistent across the entire recording.
    """

    def __init__(self, transcriber, force_aligner, diarizer, chunk_duration_sec=20):
        """
        Args:
            transcriber (CanaryTranscriber): Your ASR object.
            force_aligner (ForceAligner): The forced alignment object.
            diarizer (Diarizer): The speaker diarization object (clustering version).
            chunk_duration_sec (int or float): Max chunk duration in seconds for splitting.
        """
        self.transcriber = transcriber
        self.force_aligner = force_aligner
        self.diarizer = diarizer
        self.chunk_duration_sec = chunk_duration_sec

    def run_inference(self, audio_filepath, text=None):
        """
        1) If text is None, we do chunk-based transcription (and alignment) to avoid OOM.
        2) Merge chunk-level transcripts into a single alignment result (with time offsets).
        3) Perform diarization on the full audio (NeMo automatically splits internally if needed).
        4) Combine diarization output with the final merged alignment items.

        Returns a dict with:
            {
              "transcription": str,
              "alignment": { "text": ..., "words": [...], "tokens": [...], "segments": [...] },
              "diarization": [ {start, duration, end, speaker}, ... ]
            }
        """
        # ----------------------------------
        # (A) Transcription + Alignment
        # ----------------------------------
        if text is not None and text.strip():
            # If the user explicitly provided final text, just align it in chunks
            logging.info("[Pipeline] Using provided text, chunk-based forced alignment only.")
            merged_alignment = self._chunk_and_align(audio_filepath, text)
            final_transcript = text
        else:
            # If no text is given, we do chunk-based transcription + alignment
            logging.info("[Pipeline] No text provided, chunk-based transcription + forced alignment.")
            final_transcript, merged_alignment = self._chunk_transcribe_and_align(audio_filepath)

        # ----------------------------------
        # (B) Diarize Full Audio
        # ----------------------------------
        logging.info("[Pipeline] Running diarization on full audio.")
        # Build a "fake" alignment_result so we can pass audio + text to diarizer
        alignment_result = {
            "audio_filepath": audio_filepath,
            "text": final_transcript,
            "words_level_ctm_filepath": None,  # Not strictly needed by diarizer
            "tokens_level_ctm_filepath": None,
            "segments_level_ctm_filepath": None,
        }
        pred_rttm = self.diarizer.diarize(alignment_result)

        # Parse diarization
        diar_segments = self._parse_rttm(pred_rttm)

        # ----------------------------------
        # (C) Assign speakers to merged alignment
        # ----------------------------------
        # We'll have a structure like alignment_data["words"] = ...
        alignment_data = merged_alignment
        alignment_data["words"] = self._assign_speakers_to_alignment(alignment_data["words"], diar_segments)
        alignment_data["tokens"] = self._assign_speakers_to_alignment(alignment_data["tokens"], diar_segments)
        alignment_data["segments"] = self._assign_speakers_to_alignment(alignment_data["segments"], diar_segments)

        # ----------------------------------
        # Final result
        # ----------------------------------
        return {
            "transcription": final_transcript,
            "alignment": alignment_data,
            "diarization": diar_segments
        }

    # -------------------------------------------------------------------
    # 1) CHUNKING + Transcription + (Optionally) Force Alignment
    # -------------------------------------------------------------------
    def _chunk_transcribe_and_align(self, audio_filepath):
        """
        Split audio, transcribe each chunk, then align each chunk with the same text.
        (Alternatively, you can do forced alignment chunk by chunk if you prefer.)
        Merges chunk transcripts into a single text, merges alignment items.

        Returns: final_transcript (str), merged_alignment (dict)
        """
        chunk_paths = self._split_audio(audio_filepath, self.chunk_duration_sec)
        all_words = []
        all_tokens = []
        all_segments = []
        offset_sec = 0.0
        final_transcript_parts = []

        for chunk_file, chunk_dur in chunk_paths:
            # 1. Transcription on chunk
            chunk_text = self.transcriber.transcribe(chunk_file)
            final_transcript_parts.append(chunk_text)

            # 2. Force align chunk
            chunk_alignment_result = self.force_aligner.align(chunk_file, chunk_text)
            # Parse alignment into memory
            chunk_alignment_data = self._parse_alignment(chunk_alignment_result)

            # Adjust times by offset
            self._shift_alignment(chunk_alignment_data, offset_sec)

            # Merge into global arrays
            all_words.extend(chunk_alignment_data["words"])
            all_tokens.extend(chunk_alignment_data["tokens"])
            all_segments.extend(chunk_alignment_data["segments"])

            offset_sec += chunk_dur

            # Clean up chunk temp file if needed
            os.remove(chunk_file)

        final_transcript = " ".join(final_transcript_parts).strip()
        merged_alignment = {
            "text": final_transcript,
            "words": all_words,
            "tokens": all_tokens,
            "segments": all_segments,
        }
        return final_transcript, merged_alignment

    def _chunk_and_align(self, audio_filepath, text):
        """
        If user has provided the final text, we only need forced alignment in chunks
        to avoid OOM. We do not do chunk-based transcription.
        """
        chunk_paths = self._split_audio(audio_filepath, self.chunk_duration_sec)
        all_words = []
        all_tokens = []
        all_segments = []
        offset_sec = 0.0

        for chunk_file, chunk_dur in chunk_paths:
            chunk_alignment_result = self.force_aligner.align(chunk_file, text)
            chunk_alignment_data = self._parse_alignment(chunk_alignment_result)
            self._shift_alignment(chunk_alignment_data, offset_sec)

            all_words.extend(chunk_alignment_data["words"])
            all_tokens.extend(chunk_alignment_data["tokens"])
            all_segments.extend(chunk_alignment_data["segments"])

            offset_sec += chunk_dur
            os.remove(chunk_file)

        merged_alignment = {
            "text": text,
            "words": all_words,
            "tokens": all_tokens,
            "segments": all_segments,
        }
        return merged_alignment

    def _split_audio(self, audio_filepath, chunk_duration_sec=600):
        """
        Splits the audio into chunks of up to `chunk_duration_sec`.
        Returns a list of tuples (chunk_file_path, chunk_duration).

        We use pydub for splitting. Each chunk is saved as a temporary .wav.
        """
        audio_seg = AudioSegment.from_file(audio_filepath)
        total_ms = len(audio_seg)
        chunk_ms = chunk_duration_sec * 1000

        chunks = []
        start_ms = 0
        idx = 0

        while start_ms < total_ms:
            end_ms = min(start_ms + chunk_ms, total_ms)
            chunk = audio_seg[start_ms:end_ms]
            chunk_duration = (end_ms - start_ms) / 1000.0

            chunk_path = f"{audio_filepath}_chunk_{idx}.wav"
            chunk.export(chunk_path, format="wav")
            chunks.append((chunk_path, chunk_duration))

            start_ms += chunk_ms
            idx += 1

        return chunks

    def _shift_alignment(self, alignment_data, offset_sec):
        """
        Shifts the start/end times in alignment_data by offset_sec, in place.
        This is useful when concatenating chunk alignments into a single timeline.
        """
        for item in alignment_data["words"]:
            item["start"] += offset_sec
            item["end"] += offset_sec
        for item in alignment_data["tokens"]:
            item["start"] += offset_sec
            item["end"] += offset_sec
        for item in alignment_data["segments"]:
            item["start"] += offset_sec
            item["end"] += offset_sec

    # -------------------------------------------------------------------
    # 2) DIARIZATION
    #    (We let Nemo handle chunking internally if audio is long.)
    # -------------------------------------------------------------------
    def _parse_rttm(self, rttm_file):
        """
        Adapted from your existing code:
        Parses RTTM lines into a list of {start, duration, end, speaker} segments.
        """
        if not os.path.exists(rttm_file):
            return []
        diar_segments = []
        with open(rttm_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 8:
                    continue
                if parts[0].upper() != "SPEAKER":
                    continue
                start = float(parts[3])
                dur = float(parts[4])
                speaker = parts[7]
                diar_segments.append({
                    "start": round(start, 3),
                    "duration": round(dur, 3),
                    "end": round(start + dur, 3),
                    "speaker": speaker
                })
        return diar_segments

    # -------------------------------------------------------------------
    # 3) MERGING DIARIZATION & ALIGNMENT
    # -------------------------------------------------------------------
    def _parse_alignment(self, alignment_result):
        """
        Reuses your standard CTM parsing logic, returning a dict with
        text, words, tokens, segments.
        """
        alignment_data = {
            "text": alignment_result.get("text", ""),
            "words": [],
            "tokens": [],
            "segments": []
        }
        w_ctm = alignment_result.get("words_level_ctm_filepath")
        t_ctm = alignment_result.get("tokens_level_ctm_filepath")
        s_ctm = alignment_result.get("segments_level_ctm_filepath")

        if w_ctm and os.path.exists(w_ctm):
            alignment_data["words"] = self._parse_ctm(w_ctm)
        if t_ctm and os.path.exists(t_ctm):
            alignment_data["tokens"] = self._parse_ctm(t_ctm)
        if s_ctm and os.path.exists(s_ctm):
            alignment_data["segments"] = self._parse_ctm(s_ctm)
        return alignment_data

    def _parse_ctm(self, ctm_file):
        items = []
        with open(ctm_file, "r", encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split()
                if len(parts) < 5:
                    continue
                start = float(parts[2])
                dur = float(parts[3])
                txt = parts[4]
                items.append({
                    "start": round(start, 3),
                    "duration": round(dur, 3),
                    "end": round(start + dur, 3),
                    "text": txt
                })
        return items

    def _assign_speakers_to_alignment(self, items, diar_segments):
        """
        For each alignment item, find the speaker segment that yields the
        largest overlap in time. If none, use 'unknown'.
        """
        for item in items:
            start = item["start"]
            end = item["end"]
            best_speaker = "unknown"
            max_overlap = 0.0

            for seg in diar_segments:
                seg_start = seg["start"]
                seg_end = seg["end"]
                overlap = min(end, seg_end) - max(start, seg_start)
                if overlap > 0 and overlap > max_overlap:
                    max_overlap = overlap
                    best_speaker = seg["speaker"]
            item["speaker"] = best_speaker
        return items
