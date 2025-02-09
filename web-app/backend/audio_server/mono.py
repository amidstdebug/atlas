from pydub import AudioSegment

# Replace "stereo_input.wav" with your input file name and format
input_file = "world.mp3"


# Load the audio file
audio_stereo = AudioSegment.from_file(input_file)

# Convert to mono (1 channel)
audio_mono = audio_stereo.set_channels(1)

# Export the mono track to a new file
output_file = f"{input_file.split('.')[0]}_mono_output.wav"
audio_mono.export(output_file, format="wav")

print(f"Converted {input_file} to mono and saved as {output_file}.")