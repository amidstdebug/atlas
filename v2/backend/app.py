import os
import io
import json
import time
import logging
from datetime import datetime
from typing import Dict
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, BackgroundTasks, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse

# from sse_starlette.sse import EventSourceResponse
import uvicorn

# import tempfile

import numpy as np
import torch
import torchaudio
import soundfile as sf

from pipeline import OnlinePipeline, OnlinePipelineConfig
from pipeline.utils import transcription_to_rttm

from minutes.minutes import get_meeting_minutes

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("diarization_server.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("diarization_server")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify your frontend URL instead of "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SpeechManager:
    def __init__(self):
        logger.info("Initializing SpeechManager")
        start_time = time.time()

        # Initialize models
        logger.info("Loading models.")

        config = OnlinePipelineConfig()
        self.pipeline = OnlinePipeline(config)

        # Audio storage settings
        self.sample_rate = 48000  # Default sample rate

        self.transcribe_duration = 2
        self.time_since_transcribe = 0
        self.save_duration = 60
        self.time_since_save = 0

        self.output_dir = Path("recorded_audio")
        self.output_dir.mkdir(exist_ok=True)

        # Create test_output directory for segment saving
        self.segments_dir = Path("test_output")
        self.segments_dir.mkdir(exist_ok=True)

        # Counters for unique filenames
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.chunk_counter = 0

        self.minutes: Optional[str] = None

        # Flags
        self.save_audio = True  # Whether to save audio chunks

        logger.info(f"SpeechManager initialized in {time.time() - start_time:.2f}s")

    def get_output_segments(self):
        transcripts = self.pipeline.get_transcription()
        if len(transcripts) > 0:
            output_segments = [
                {
                    'speaker': transcript.label,
                    'start': transcript.segment.start,
                    'end': transcript.segment.end,
                    'duration': transcript.segment.end - transcript.segment.start,
                    'text': transcript.text,
                    'id': transcript.id
                }
                for transcript in transcripts
            ]
        else:
            # Format segments for JSON response
            annotation = self.pipeline.get_annotation()
            output_segments = [
                {
                    'speaker': label,
                    'start': segment.start,
                    'end': segment.end,
                    'duration': segment.end - segment.start,
                    'text': f"[{label} audio]"
                }
                for segment, _, label in annotation.itertracks(yield_label=True)
            ]

        return output_segments

    def process_chunk(self, waveform: np.ndarray, transcribe=True, save=False) -> Dict:
        """Process a single chunk of audio and return diarization results."""
        chunk_start_time = time.time()
        logger.info(f"Processing chunk: {len(waveform)} samples")

        try:
            # waveform is processed as in the original code...
            increment_duration = waveform.shape[0]
            self.time_since_transcribe += increment_duration
            self.time_since_save += increment_duration

            waveform = np.expand_dims(waveform, 1)
            self.pipeline(waveform, self.sample_rate)

            if transcribe:
                if self.time_since_transcribe > self.transcribe_duration * self.sample_rate:
                    self.pipeline.transcribe()
                    self.time_since_transcribe = 0

            if save:
                if self.time_since_save > self.save_duration * self.sample_rate:
                    pipeline_sample_rate = self.pipeline.get_pipeline().config.sample_rate
                    pipeline_waveform = torch.from_numpy(self.pipeline.waveform).permute(1, 0)
                    torchaudio.save(f"recorded_audio/save_{time.time()}.wav", pipeline_waveform, pipeline_sample_rate)
                    self.time_since_save = 0

            output_segments = self.get_output_segments()

            total_time = time.time() - chunk_start_time
            logger.info(f"Processing complete: {len(output_segments)} segments in {total_time:.2f}s")

            return {
                "segments": output_segments
            }
        except Exception as e:
            logger.error(f"Chunk processing error: {e}", exc_info=True)
            return {
                "segments": []
            }

    def new_session(self):
        speech_parser.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        speech_parser.chunk_counter = 0
        speech_parser.time_since_transcribe = 0
        speech_parser.time_since_save = 0
        logger.info(f"New session: {speech_parser.session_id}")

    def create_minutes(self):
        self.minutes = get_meeting_minutes(self.pipeline.get_transcription(), use_anthropic=True)

# Create a single instance of the speech manager
logger.info("Starting speech diarization server")
speech_parser = SpeechManager()

@app.websocket("/ws/call")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    client_id = id(websocket)
    logger.info(f"Client connected: {client_id}")

    session_start_time = time.time()

    try:
        # Generate a new session ID for each connection
        speech_parser.new_session()

        message_count = 0
        chunk_count = 0

        while True:
            # Receive message
            message = await websocket.receive()
            message_count += 1

            # Handle configuration or JSON data
            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    # Configuration message
                    if "type" in data and data["type"] == "config":
                        # Update sample rate from client config
                        speech_parser.sample_rate = data.get("sampleRate", 44100)
                        logger.info(f"Config received: sample rate={speech_parser.sample_rate}Hz")
                        await websocket.send_json({"status": "config_received"})
                        continue
                except json.JSONDecodeError:
                    logger.warning("Invalid JSON received")
                    pass

            # Handle binary audio data
            if "bytes" in message:
                # Get the binary data and convert to float32 array
                audio_bytes = message["bytes"]
                audio_array = np.frombuffer(audio_bytes, dtype=np.float32)

                chunk_count += 1
                chunk_size_seconds = len(audio_array) / speech_parser.sample_rate
                logger.info(f"Chunk #{chunk_count}: {chunk_size_seconds:.2f}s audio")

                # Process audio chunk
                chunk_start = time.time()
                results = speech_parser.process_chunk(audio_array)
                chunk_process_time = time.time() - chunk_start

                # Send results if there are segments
                if "segments" in results:
                    num_segments = len(results["segments"])
                    logger.info(f"Sending {num_segments} segments to client ({chunk_process_time:.2f}s)")
                    await websocket.send_json(results)
                else:
                    raise RuntimeError('Response from speech_parser does not have key "segments".')

    except WebSocketDisconnect:
        session_duration = time.time() - session_start_time
        logger.info(f"Client {client_id} disconnected. Stats: {session_duration:.2f}s, {chunk_count} chunks")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        await websocket.close(code=1001, reason=str(e))

@app.post("/reset")
async def reset_pipeline():
    """Reset the diarization pipeline to its initial state."""
    try:
        speech_parser.pipeline.reset()

        # Also reset session-specific information
        speech_parser.new_session()

        logger.info(f"Pipeline reset. New session: {speech_parser.session_id}")

        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": "Pipeline reset successfully", "new_session_id": speech_parser.session_id}
        )
    except Exception as e:
        logger.error(f"Error resetting pipeline: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to reset pipeline: {str(e)}"}
        )

@app.post("/reannotate")
async def redo_annotation():
    """Reset the diarization pipeline to its initial state."""
    try:
        speech_parser.pipeline.reannotate()

        logger.info("Transcript reannotated.")

        return JSONResponse(
            status_code=200,
            content={"status": "success", "message": "Pipeline reannotated successfully"}
        )
    except Exception as e:
        logger.error(f"Error resetting pipeline: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to reset pipeline: {str(e)}"}
        )

@app.get("/download/rttm")
async def download_rttm():
    """Download the current transcription as an RTTM file."""
    try:
        # Get the current transcription
        transcripts = speech_parser.pipeline.get_transcription()

        if not transcripts:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "No transcription data available"}
            )

        # Generate RTTM content with current session ID as file_id
        rttm_content = transcription_to_rttm(transcripts, file_id=speech_parser.session_id)

        # Create filename with session ID and timestamp
        filename = f"transcript_{speech_parser.session_id}.rttm"

        # Return the RTTM content as a downloadable file
        from fastapi.responses import Response
        return Response(
            content=rttm_content,
            media_type="text/plain",
            headers={
                "Content-Disposition": f"attachment; filename={filename}"
            }
        )
    except Exception as e:
        logger.error(f"Error generating RTTM file: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to generate RTTM file: {str(e)}"}
        )

@app.get("/segments")
async def get_segments():
    try:
        output_segments = speech_parser.get_output_segments()

        return JSONResponse(
            status_code=200,
            content={
                "segments": output_segments
            }
        )
    except Exception as e:
        logger.error(f"Error getting segments: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to get segments: {str(e)}"}
        )

def create_audio_file(waveform, sample_rate, filename_prefix, file_description=""):
    try:
        # Check if the waveform is mono or has a channel dimension
        if len(waveform.shape) == 1:
            # Add a channel dimension for mono audio
            waveform_tensor = torch.from_numpy(waveform).unsqueeze(0)
        else:
            # Convert from (length, channel) to (channel, length)
            waveform_tensor = torch.from_numpy(waveform).transpose(0, 1)
            
        # Create a temporary file
        temp_dir = Path("temp_audio")
        temp_dir.mkdir(exist_ok=True)
        
        timestamp = int(time.time())
        temp_filename = f"{filename_prefix}_{speech_parser.session_id}_{timestamp}.wav"
        temp_path = temp_dir / temp_filename
        
        # Save the audio to the file
        torchaudio.save(str(temp_path), waveform_tensor, sample_rate)
        
        # Log file creation
        duration = len(waveform) / sample_rate
        logger.info(f"Created {file_description} audio file at {temp_path} ({duration:.2f}s)")
        
        return temp_path, None
    except Exception as e:
        error_msg = f"Error creating audio file: {str(e)}"
        logger.error(error_msg, exc_info=True)
        return None, error_msg

def cleanup_temp_file(temp_path, delay=2):
    """Background task to clean up temporary files after they're served."""
    try:
        # Add a delay to ensure the file is fully sent before deletion
        time.sleep(delay)
        if temp_path.exists():
            temp_path.unlink()
            logger.info(f"Cleaned up temporary file: {temp_path}")
    except Exception as e:
        logger.error(f"Error cleaning up temp file {temp_path}: {e}")

@app.get("/segments/{segment_id}/audio")
async def get_segment_audio(segment_id: str, background_tasks: BackgroundTasks):
    """Return the audio waveform for a specific transcription segment by ID."""
    temp_path = None
    try:
        # Find the segment with the matching ID
        transcripts = speech_parser.pipeline.get_transcription()

        # Find the target segment
        target_segment = None
        for transcript in transcripts:
            if transcript.id == segment_id:
                target_segment = transcript
                break

        if speech_parser.pipeline.waveform is None or len(speech_parser.pipeline.waveform) == 0:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "No audio data available"}
            )

        if not target_segment:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": f"Segment with ID {segment_id} not found"}
            )

        # Extract timing information
        sample_rate = speech_parser.pipeline.get_pipeline().config.sample_rate
        start_idx = int(target_segment.segment.start * sample_rate)
        end_idx = int(target_segment.segment.end * sample_rate)

        # Ensure indices are within bounds
        start_idx = max(0, start_idx)
        end_idx = min(len(speech_parser.pipeline.waveform), end_idx)

        # Extract the segment waveform
        segment_waveform = speech_parser.pipeline.waveform[start_idx:end_idx]

        # Create the audio file
        temp_path, error = create_audio_file(
            segment_waveform,
            sample_rate,
            f"segment_{segment_id}",
            f"segment {segment_id}"
        )

        if error:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": error}
            )

        # Add cleanup task
        background_tasks.add_task(cleanup_temp_file, temp_path)

        # Return the WAV file
        return FileResponse(
            path=str(temp_path),
            media_type="audio/wav",
            filename=f"segment_{segment_id}.wav"
        )

    except Exception as e:
        logger.error(f"Error extracting segment audio: {e}", exc_info=True)
        # Clean up temp file if it exists
        if temp_path and Path(temp_path).exists():
            try:
                Path(temp_path).unlink()
            except Exception:
                pass

        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to extract segment audio: {str(e)}"}
        )

@app.get("/download/audio")
async def download_full_audio(background_tasks: BackgroundTasks):
    """Download the full audio waveform as a WAV file."""
    temp_path = None
    try:
        # Check if we have any audio data
        if speech_parser.pipeline.waveform is None or len(speech_parser.pipeline.waveform) == 0:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "No audio data available"}
            )

        # Get the pipeline sample rate
        sample_rate = speech_parser.pipeline.get_pipeline().config.sample_rate

        # Get the full waveform
        full_waveform = speech_parser.pipeline.waveform

        # Create the audio file
        temp_path, error = create_audio_file(
            full_waveform,
            sample_rate,
            "full_recording",
            "full recording"
        )

        if error:
            return JSONResponse(
                status_code=500,
                content={"status": "error", "message": error}
            )

        # Add cleanup task with longer delay for potentially larger files
        background_tasks.add_task(cleanup_temp_file, temp_path, delay=5)

        # Return the WAV file
        return FileResponse(
            path=str(temp_path),
            media_type="audio/wav",
            filename=f"recording_{speech_parser.session_id}.wav"
        )

    except Exception as e:
        logger.error(f"Error creating full audio file: {e}", exc_info=True)
        # Clean up temp file if it exists
        if temp_path and Path(temp_path).exists():
            try:
                Path(temp_path).unlink()
            except Exception:
                pass

        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to create audio file: {str(e)}"}
        )

@app.post("/upload/audio")
async def upload_audio(file: UploadFile = File(...)):
    """
    Upload an audio file for processing.
    The endpoint resets the pipeline, then processes the file in chunks.
    """
    try:
        logger.info(f"Receiving uploaded audio file: {file.filename}")

        # Read the file content
        content = await file.read()

        # Reset the pipeline first
        speech_parser.pipeline.reset()
        speech_parser.new_session()

        # Load audio data using soundfile
        with io.BytesIO(content) as audio_buffer:
            # Read audio data
            data, samplerate = sf.read(audio_buffer)
            data = data.astype(np.float32)

            logger.info(f"Processing with sample rate: {samplerate}")

            # Convert to mono if needed
            if len(data.shape) > 1 and data.shape[1] > 1:
                data = data.mean(axis=1)

            speech_parser.sample_rate = samplerate
            speech_parser.process_chunk(data, transcribe=False)
            speech_parser.pipeline.transcribe()

            return {
                "status": "success",
                "message": f"Processed audio file: {file.filename}",
                "session_id": speech_parser.session_id,
                "duration": len(data) / speech_parser.sample_rate
            }

    except Exception as e:
        logger.error(f"Error processing uploaded file: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process audio file: {str(e)}"
        )

@app.post("/minutes")
async def create_minutes():
    """
    Generate meeting minutes from the current transcription.
    """
    try:
        # Get the current transcription
        transcripts = speech_parser.pipeline.get_transcription()

        if not transcripts:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "No transcription data available for minutes generation"}
            )

        # Generate minutes using the get_meeting_minutes function
        speech_parser.create_minutes()

        return JSONResponse(
            status_code=200,
            content={
                "status": "success", 
                "message": "Meeting minutes created successfully"
            }
        )
    except Exception as e:
        logger.error(f"Error generating meeting minutes: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to generate meeting minutes: {str(e)}"}
        )

@app.get("/download/minutes")
async def download_minutes(background_tasks: BackgroundTasks):
    """
    Download the generated meeting minutes as a PDF file.
    """
    try:
        if not speech_parser.minutes:
            return JSONResponse(
                status_code=404,
                content={"status": "error", "message": "No meeting minutes are available. Please create minutes first."}
            )
        
        # Create a temporary directory to store the files
        temp_dir = Path("temp_minutes")
        temp_dir.mkdir(exist_ok=True)
        
        timestamp = int(time.time())
        md_filename = f"minutes_{speech_parser.session_id}_{timestamp}.md"
        pdf_filename = f"minutes_{speech_parser.session_id}_{timestamp}.pdf"
        md_path = temp_dir / md_filename
        pdf_path = temp_dir / pdf_filename
        
        # Write the markdown content to a temp file
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(speech_parser.minutes)
        
        # Convert markdown to HTML
        import markdown
        html_content = markdown.markdown(speech_parser.minutes)
        
        # Create a simple HTML document with some basic styling
        full_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <title>Meeting Minutes</title>
            <style>
                body {{ 
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    margin: 40px;
                }}
                h1, h2, h3 {{ color: #333; }}
                h1 {{ border-bottom: 1px solid #ddd; padding-bottom: 10px; }}
                table {{ border-collapse: collapse; width: 100%; margin: 20px 0; }}
                th, td {{ border: 1px solid #ddd; padding: 8px; }}
                th {{ background-color: #f2f2f2; }}
            </style>
        </head>
        <body>
            {html_content}
        </body>
        </html>
        """
        
        # Convert HTML to PDF
        from weasyprint import HTML
        HTML(string=full_html).write_pdf(pdf_path)
        
        logger.info(f"Created meeting minutes PDF at {pdf_path}")
        
        # Add cleanup tasks for both files
        background_tasks.add_task(cleanup_temp_file, md_path, delay=5)
        background_tasks.add_task(cleanup_temp_file, pdf_path, delay=5)
        
        # Return the PDF file
        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=f"minutes_{speech_parser.session_id}.pdf"
        )
    except Exception as e:
        logger.error(f"Error generating PDF meeting minutes: {e}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={"status": "error", "message": f"Failed to generate PDF meeting minutes: {str(e)}"}
        )

if __name__ == "__main__":
    logger.info("Server starting on 0.0.0.0:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000)
