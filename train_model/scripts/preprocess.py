import os
import ffmpeg
import subprocess
import datetime
import torch
import shutil
import re

# Load Silero VAD model
model, utils = torch.hub.load(repo_or_dir='snakers4/silero-vad', model='silero_vad', trust_repo=True)

# Access tuple elements using correct indices
get_speech_timestamps = utils[0]
save_audio = utils[1]
read_audio = utils[2]


def get_audio_volume(log_file, file_path):
    """
    Get the average volume of a WAV file using ffmpeg.

    :param file_path: Path to the audio file
    :return: The average volume in dB
    """
    try:
        result = subprocess.run(
            ['ffmpeg', '-i', file_path, '-filter:a', 'volumedetect', '-f', 'null', '-'],
            stderr=subprocess.PIPE,
            text=True
        )
        output = result.stderr

        # Search for the average volume in the output
        for line in output.split('\n'):
            if 'mean_volume' in line:
                volume_db = float(line.split('mean_volume:')[1].split(' ')[1])
                return volume_db
    except Exception as e:
        log_message(log_file, f"Error getting volume for {file_path}: {str(e)}")
    return None


def log_message(log_file, message):
    """
    Log messages to the provided log file with a timestamp using local time.

    :param log_file: Path to the log file.
    :param message: Log message to be written to the file.
    """
    local_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_file, 'a') as log_file_obj:
        log_file_obj.write(f"{local_time} - {message}\n")


def delete_file_variants(base_name, audio_dir, output_dir, log_file):
    """
    Delete all variants of a file (boosted, cleaned, temporary, and the original file).

    :param base_name: Base file name (without extensions).
    :param audio_dir: Directory where the original files are stored.
    :param output_dir: Directory where processed files are stored.
    :param log_file: Log file to log the deletions.
    """
    # Define all file variants to delete
    file_variants = [
        os.path.join(output_dir, f"{base_name}_boosted.wav"),
        os.path.join(output_dir, f"{base_name}_cleaned.wav"),
        os.path.join(output_dir, f"temp_trimmed_{base_name}_cleaned.wav"),
        os.path.join(output_dir, f"temp_padded_{base_name}_cleaned.wav")
    ]

    # Loop through each file variant and delete if it exists
    for file_path in file_variants:
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                log_message(log_file, f"Deleted {file_path}")
            except Exception as e:
                log_message(log_file, f"Failed to delete {file_path}: {str(e)}")


def adjust_audio_volume(file_path, output_dir, log_file, target_db=-4.0, limiter_db=-2.0):
    """
    Adjust the volume of a WAV file to match the target average volume, apply hard limiting at -2dB,
    compress if needed, and ensure the sample rate is set to 16000 Hz.

    :param file_path: Path to the audio file
    :param output_dir: Directory where the adjusted audio file will be saved
    :param log_file: Path to the log file
    :param target_db: The target average volume in dB
    :param limiter_db: The hard limit in dB
    """
    current_volume = get_audio_volume(log_file, file_path)

    if current_volume is not None:
        # Calculate the volume adjustment required
        volume_adjustment = target_db - current_volume

        # Create output path in the new directory with _boosted suffix
        base_name = os.path.basename(file_path).replace(".wav", "")
        output_path = os.path.join(output_dir, f"{base_name}_boosted.wav")

        log_message(log_file, f"Current volume of {file_path}: {current_volume}dB")
        log_message(log_file, f"Volume adjustment needed: {volume_adjustment}dB")

        try:
            # Adjust the volume by boosting it and applying a limiter at -2dB, with sample rate set to 16000 Hz
            (
                ffmpeg.input(file_path)
                .filter('volume', f'{volume_adjustment}dB')  # Boost volume
                .filter('acompressor', threshold=f'{limiter_db}dB', ratio=3.0)  # Compression if needed
                .filter('alimiter', limit=f'{limiter_db}dB')  # Apply hard limiter at -2dB
                .output(output_path, ar=16000)  # Ensure sample rate is 16000 Hz
                .overwrite_output()  # Overwrite if already exists
                .run()
            )

            log_message(log_file,
                        f"Adjusted {file_path} by {volume_adjustment}dB, applied hard limiting at {limiter_db}dB.")
            log_message(log_file, f"Saved adjusted file to {output_path}")
        except Exception as e:
            log_message(log_file, f"Error adjusting volume for {file_path}: {str(e)}")

        return output_path  # Return the path to the boosted file
    else:
        log_message(log_file, f"Skipping {file_path} due to volume detection error.")
        return None


def get_audio_duration(file_path):
    """
    Get the duration of an audio file using ffmpeg.

    :param file_path: Path to the audio file.
    :return: Duration in seconds.
    """
    try:
        probe = ffmpeg.probe(file_path)
        return float(probe['format']['duration'])
    except Exception as e:
        return None


def trim_and_pad_audio(file_path, output_dir, log_file, audio_dir):
    """
    Detects the start of speech using VAD, cuts everything before it, and pads the audio to 30 seconds.
    Ensures sample rate is set to 16000 Hz. If no speech is detected, all variants of the file are deleted.

    :param file_path: Path to the audio file
    :param output_dir: Directory where the adjusted audio file will be saved
    :param log_file: Path to the log file
    :param audio_dir: Directory where the original audio files are stored
    """
    audio = read_audio(file_path, sampling_rate=16000)
    # Remove both ".wav" and "_boosted" from the file name
    base_name = re.sub(r'_boosted$', '', os.path.basename(file_path).replace(".wav", ""))

    # Get speech timestamps using VAD model
    speech_timestamps = get_speech_timestamps(audio, model, sampling_rate=16000)

    # If no speech is detected, delete all variants of the file, including the original file
    if not speech_timestamps:
        log_message(log_file, "No speech detected, deleting all file remnants.")
        delete_file_variants(base_name, audio_dir, output_dir, log_file)
        return

    # Log VAD detection
    log_message(log_file, f"VAD detected speech starting at {speech_timestamps[0]['start'] / 16000.0:.2f} seconds.")

    # Get the start of the first speech segment
    start_time = speech_timestamps[0]['start'] / 16000.0  # Convert from samples to seconds

    # Generate the cleaned file name without the '_boosted' suffix
    cleaned_output_path = os.path.join(output_dir, f"{base_name}_cleaned.wav")
    temp_trimmed_path = os.path.join(output_dir, f"temp_trimmed_{base_name}_cleaned.wav")
    temp_padded_path = os.path.join(output_dir, f"temp_padded_{base_name}_cleaned.wav")

    try:
        # Step 1: Trim audio before the start of speech and save to a temporary file with 16000 Hz sample rate
        ffmpeg.input(file_path, ss=start_time).output(temp_trimmed_path, ar=16000).overwrite_output().run()
        log_message(log_file, f"Trimmed audio before {start_time} seconds.")

        # Step 2: Get the duration of the trimmed audio
        duration = get_audio_duration(temp_trimmed_path)
        if duration is None:
            log_message(log_file, f"Could not determine duration of {temp_trimmed_path}")
            return

        padding_needed = max(0, 30 - duration)

        if padding_needed > 0:
            # Pad the audio with the required duration and ensure sample rate is 16000 Hz
            ffmpeg.input(temp_trimmed_path).filter('apad', pad_dur=padding_needed).output(temp_padded_path, ar=16000).overwrite_output().run()
            log_message(log_file, f"Padded the audio to 30 seconds.")
        else:
            # No padding needed; copy the trimmed audio
            shutil.copy(temp_trimmed_path, temp_padded_path)
            log_message(log_file, f"Audio is already 30 seconds or longer; no padding applied.")

        # Move the padded file to the final destination without the '_boosted' suffix
        shutil.move(temp_padded_path, cleaned_output_path)
        log_message(log_file, f"Saved cleaned audio to {cleaned_output_path}")

    except Exception as e:
        log_message(log_file, f"Error during trimming and padding: {str(e)}")

    finally:
        # Clean up temporary files
        if os.path.exists(temp_trimmed_path):
            os.remove(temp_trimmed_path)
        if os.path.exists(temp_padded_path):
            os.remove(temp_padded_path)

        # Delete the boosted version
        boosted_file = os.path.join(output_dir, f"{base_name}_boosted.wav")
        if os.path.exists(boosted_file):
            os.remove(boosted_file)
            log_message(log_file, f"Deleted {boosted_file} to keep only the final cleaned file.")

def process_audio_files(audio_path, output_path, log_path, target_db=-4.0, limiter_db=-2.0):
    """
    Process all WAV files in the directory, adjust their volume to match the target average volume,
    apply a hard limit at -2dB, and compress if needed. Then apply VAD and pad to 30 seconds.
    Save the cleaned files to a new directory. If no speech is detected, all file remnants are deleted.

    :param audio_path: Directory containing the WAV files
    :param output_path: Directory where the cleaned files will be saved
    :param log_path: Directory where logs are saved
    :param target_db: The target average volume in dB
    :param limiter_db: The hard limit in dB
    """
    os.makedirs(output_path, exist_ok=True)  # Create the output directory if it doesn't exist
    os.makedirs(log_path, exist_ok=True)  # Create the log directory if it doesn't exist

    for audio_file in os.listdir(audio_path):
        if audio_file.endswith(".wav"):
            file_path = os.path.join(audio_path, audio_file)

            # Create the log file for this specific audio file, with timestamp
            base_name = os.path.basename(file_path).replace(".wav", "")
            log_file = os.path.join(log_path,
                                    f"{base_name}_{datetime.datetime.now().strftime('%Y-%m-%d_%H-%M-%S')}.log")

            # Step 1: Adjust the volume of the audio
            boosted_file_path = adjust_audio_volume(file_path, output_path, log_file, target_db, limiter_db)

            # Step 2: Apply VAD and padding if volume adjustment was successful
            if boosted_file_path:
                trim_and_pad_audio(boosted_file_path, output_path, log_file, audio_path)


if __name__ == "__main__":
    audio_dir = "../data/train"  # Directory containing the original WAV files
    cleaned_dir = "../data/train_cleaned"  # Directory to save the cleaned WAV files
    log_path = "../logs/preprocess"  # Base directory for logs, specifically in ../logs/preprocess
    target_db = -6.0  # Target average volume in dB
    limiter_db = -2.0  # Hard limit in dB

    process_audio_files(audio_dir, cleaned_dir, log_path, target_db, limiter_db)
