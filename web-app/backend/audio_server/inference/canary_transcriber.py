# canary_transcriber.py
from nemo.collections.asr.models import EncDecMultiTaskModel

class CanaryTranscriber:
    def __init__(self, model_name: str = 'nvidia/canary-1b'):
        # Load the Canary ASR model from NeMo pretrained models.
        self.model = EncDecMultiTaskModel.from_pretrained(model_name)
        # Update the decoding configuration (beam size etc)
        decode_cfg = self.model.cfg.decoding
        decode_cfg.beam.beam_size = 1
        self.model.change_decoding_strategy(decode_cfg)
        self.model.eval()

    def transcribe(self, audio_filepath: str) -> str:
        """
        Transcribes the given audio file.
        Returns a single string (the transcription).
        """
        result = self.model.transcribe(audio_filepath)
        # In our example, the model returns a list of hypotheses.
        if isinstance(result, list):
            return result[0]
        return result
