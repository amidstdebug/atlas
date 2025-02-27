import torch
from utils import load_audio
from nemo.collections.asr.models.label_models import EncDecSpeakerLabelModel

from speech_parser import Audio, SileroVAD, OnlineSpeakerClustering, MSDD, OnlineDiarizationPipeline

def simple_diarization_example():
    # 1. Load the required models
    msdd_model = MSDD(
        threshold=0.8
    )
    speech_model = msdd_model.speech_embedding_model
    vad_model = SileroVAD(threshold=0.5)
    clustering = OnlineSpeakerClustering()
    
    # 2. Initialize the diarization pipeline
    diarizer = OnlineDiarizationPipeline(
        speech_embedding_model=speech_model,
        voice_activity_detection_model=vad_model,
        multi_scale_diarization_model=msdd_model,
        speaker_clustering=clustering
    )
    
    # 3. Load an audio file
    audio_path = "toefl_eg.mp3"
    waveform, sr = load_audio(audio_path)
    waveform = waveform[0]
    
    # 4. Process audio in chunks (simulating streaming)
    chunk_size = int(16000 * 2.5)  # 5 second chunks at 16kHz
    for i in range(0, len(waveform), chunk_size):
        chunk = waveform[i:min(i+chunk_size, len(waveform))]
        
        # Process the chunk
        probs, labels = diarizer(chunk)
        
        # Optional: get intermediate results
        if i % (chunk_size * 6) == 0:  # Every 30 seconds
            current_segments = diarizer.get_merged_speaker_segments(use_cache=False)
            print(f"At {i/16000:.1f}s: {len(current_segments)} speaker segments")
    
    # 5. Get final diarization results
    speaker_segments = diarizer.get_merged_speaker_segments()
    
    # 6. Print the results
    for i, segment in enumerate(speaker_segments):
        torchaudio.save(f"test_output/segment_{i+1}_{segment.speaker}_{segment.start}", segment.data.unsqueeze(0).cpu(), 16_000)
        print(f"Segment {i+1}: Speaker {segment.speaker}, "
              f"Time: {segment.start:.2f}s - {segment.start + segment.duration:.2f}s")
    
    # 7. Optional: Re-cluster and get updated results
    print("\nRediarizing with updated clustering...")
    diarizer.rediarize()
    updated_segments = diarizer.get_merged_speaker_segments()
    
    for i, segment in enumerate(updated_segments):
        torchaudio.save(f"test_output/updated_segment_{i+1}_{segment.speaker}_{segment.start}", segment.data.unsqueeze(0).cpu(), 16_000)
        print(f"Updated Segment {i+1}: Speaker {segment.speaker}, "
              f"Time: {segment.start:.2f}s - {segment.start + segment.duration:.2f}s")
    
    return speaker_segments

if __name__ == "__main__":
    simple_diarization_example()