from utils import load_audio

waveform, sample_rate = load_audio('toefl_eg.mp3')

from diart_pipeline import OnlinePipeline, OnlinePipelineConfig
pipe_config = OnlinePipelineConfig()
pipe = OnlinePipeline(pipe_config)

pipe(waveform.permute(1, 0).numpy()[:10*16000])

pipe.transcribe()

print(pipe._transcriptions)


pipe(waveform.permute(1, 0).numpy()[10*16000:20*16000])

pipe.transcribe()

print(pipe._transcriptions)


pipe(waveform.permute(1, 0).numpy()[20*16000:30*16000])

pipe.transcribe()

print(pipe._transcriptions)