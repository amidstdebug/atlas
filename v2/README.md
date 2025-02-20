# Atlas V2

Now with 100% more diarization

# Todo
1. Tweak [online_clustering.py](backend/diarizer/clustering/online_clustering.py) to set a min. number of samples before clustering to prevent '''over-clustering'''
2. Tune the segment merging code in [app.py](backend/app.py) (probably split that off into another file)
3. Add functions to re-diarize the entire sequence if it sufficiently changes
4. Add [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
