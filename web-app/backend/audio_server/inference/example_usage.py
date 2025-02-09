# example_usage.py

from pipeline import ASRAlignmentPipeline

if __name__ == "__main__":
    pipeline = ASRAlignmentPipeline(
        canary_model_name="nvidia/canary-1b",
        canary_beam_size=1,
        forced_alignment_model="stt_en_conformer_ctc_large",
        device="cuda"
    )

    audio_path = "../data/an4_diarize_test.wav"
    reference_text = None  # or "some known reference text"

    result = pipeline.run_pipeline(audio_path, reference_text=reference_text)
    print("Final transcript:", result["transcript"])
    print("Alignment outputs in:", result["alignment_dir"])