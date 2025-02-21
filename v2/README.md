# Atlas V2

Now with 100% more diarization

# Todo
1. Add functions to re-diarize the entire sequence if it sufficiently changes
2. Add [faster-whisper](https://github.com/SYSTRAN/faster-whisper)
3. Clustering tweaks
    * Clustering is still really inconsistent
    * Clustering for every iter slows the process down a lot
        * If clustering is not done every step, then the MSDD process has to be changed since it falls back to the clustering algo
