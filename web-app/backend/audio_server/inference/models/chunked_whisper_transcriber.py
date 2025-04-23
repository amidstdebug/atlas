import os
from tqdm import tqdm

from inference.models.whisper_transcriber import WhisperTranscriber
from inference.models.force_aligner import ForceAligner

from pydub import AudioSegment

class ChunkedWhisperTranscriber:
    def __init__(self, model_name: str = 'jlvdoorn/whisper-medium.en-atco2-asr'):
        self.transcriber = WhisperTranscriber(model_name=model_name)
        self.aligner = ForceAligner()
        print(f"ChunkedWhisperTranscriber initialized with model: {model_name}")

    def __split_audio(self, audio_filepath, chunk_duration_sec=600):
        """
        Splits the audio into chunks of up to `chunk_duration_sec`.
        Returns a list of tuples (chunk_file_path, chunk_start_sec, chunk_duration_sec).
        """
        audio_seg = AudioSegment.from_file(audio_filepath)

        audio_seg = audio_seg.set_channels(1)

        total_ms = len(audio_seg)
        chunk_ms = chunk_duration_sec * 1000

        chunks = []
        start_ms = 0
        idx = 0

        while start_ms < total_ms:
            end_ms = min(start_ms + chunk_ms, total_ms)
            chunk = audio_seg[start_ms:end_ms]

            # The absolute start time of this chunk in the original audio
            chunk_start_sec = start_ms / 1000.0
            # The duration of *this* chunk
            chunk_length_sec = (end_ms - start_ms) / 1000.0

            # Write chunk to disk
            chunk_path = f"{audio_filepath}_chunk_{idx}.wav"
            chunk.export(chunk_path, format="wav")

            # Store all three: path, absolute start, and chunk duration
            chunks.append((chunk_path, chunk_start_sec, chunk_length_sec))

            start_ms += chunk_ms
            idx += 1

        return chunks

    def transcribe(self, audio_filepath, chunk_duration_sec=30):
        # Split into chunks
        chunk_infos = self.__split_audio(audio_filepath, chunk_duration_sec)

        all_words = []
        all_tokens = []
        all_segments = []
        final_transcript_parts = []

        for chunk_file, chunk_start_sec, chunk_dur in tqdm(chunk_infos):
            # 1. Transcribe chunk with Whisper
            chunk_text = self.transcriber.transcribe(chunk_file)
            final_transcript_parts.append(chunk_text)

            # 2. Force align chunk
            alignment_result = self.aligner.align(chunk_file, chunk_text)
            chunk_alignment_data = self.__parse_alignment(alignment_result)

            # IMPORTANT: shift by the *absolute* start of the chunk
            self.__shift_alignment(chunk_alignment_data, chunk_start_sec)

            # 3. Merge into global arrays
            all_words.extend(chunk_alignment_data["words"])
            all_tokens.extend(chunk_alignment_data["tokens"])
            all_segments.extend(chunk_alignment_data["segments"])

            # optionally remove chunk file
            os.remove(chunk_file)

        final_transcript = " ".join(final_transcript_parts).strip()

        merged_alignment = {
            "text": final_transcript,
            "words": all_words,
            "tokens": all_tokens,
            "segments": all_segments,
        }

        return merged_alignment


    def __parse_ctm(self, ctm_file):
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


    def __parse_alignment(self, alignment_result):
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
            alignment_data["words"] = self.__parse_ctm(w_ctm)
        if t_ctm and os.path.exists(t_ctm):
            alignment_data["tokens"] = self.__parse_ctm(t_ctm)
        if s_ctm and os.path.exists(s_ctm):
            alignment_data["segments"] = self.__parse_ctm(s_ctm)
        return alignment_data

    def __shift_alignment(self, alignment_data, offset_sec):
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