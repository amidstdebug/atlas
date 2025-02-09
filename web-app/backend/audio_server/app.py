import os

# Set the cache directories before importing any NeMo-related modules.
os.environ['NEMO_CACHE_DIR'] = os.path.join(os.path.dirname(__file__), 'models')
os.environ['HF_HOME'] = os.path.join(os.path.dirname(__file__), 'hf_cache')

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.responses import JSONResponse
from inference.asr_infer import ASRDiarizationInference
import uvicorn

app = FastAPI(title="ASR with Speaker Diarization API")

# Define the base directory for storing data (and config) files.
BASE_DIR = os.getcwd()
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 1) Create a single instance of our class-based inference, 
#    which will load and cache the heavy model in memory.
inference_engine = ASRDiarizationInference(
	config_dir=DATA_DIR,
	domain_type="meeting"
)

@app.post("/infer")
async def infer(audio: UploadFile = File(...)):
	"""
	Endpoint to perform ASR + Speaker Diarization inference.
	Expects a WAV file upload. The file is saved to the data folder.
	A manifest file is created internally and used to run the NeMo pipeline.
	"""
	# Validate file type – only WAV files are supported.
	if audio.content_type not in ["audio/wav", "audio/x-wav", "audio/wave"]:
		raise HTTPException(status_code=400, detail="Invalid audio file type. Only WAV files are accepted.")

	# Save the uploaded audio file to persistent data folder.
	file_path = os.path.join(DATA_DIR, audio.filename)
	with open(file_path, "wb") as f:
		content = await audio.read()
		f.write(content)

	result = inference_engine.infer(file_path)
	# try:
	# 	# 2) Perform inference using the cached model and a fresh ephemeral run.
	# except Exception as e:
	# 	print(e)
	# 	raise HTTPException(
	# 		status_code=500,
	# 		detail=f"Inference error: {str(e)}"
	# 	)

	return JSONResponse(content=result)

if __name__ == "__main__":
	uvicorn.run(app, host="0.0.0.0", port=8889)
