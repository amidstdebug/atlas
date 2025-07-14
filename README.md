# ATLAS (Automated Transmission Language Analysis System)

ATLAS is a powerful application designed to transcribe live ATC (Air Traffic Control) communications and provide real-time situational reports (SITREPs). Additionally, it includes a meeting minutes feature that supports live recording and file uploads for detailed, automated transcription. The system leverages cutting-edge AI technologies, a streamlined architecture, and modern containerization for scalability and ease of use.

![](https://github.com/amidstdebug/atlas/blob/main/live.gif)

---

## Features

### 1. **ATC Mode**
- **Live Transcription**: Transcribes live ATC communications in real-time.
- **Evolving SITREP**: Provides a continuously updated situational report based on ongoing communications.
- **File Upload**: Supports transcription of pre-recorded ATC communications.

### 2. **Meeting Minutes**
- **Live Recording**: Transcribes meeting minutes in real-time.
- **File Upload**: Upload recorded meetings for automated transcription and summary.

### 3. **Customizable Models**
- Allows users to select the size of the Llama 3.1 LLM model used for transcription and analysis, depending on performance requirements.

---

## Technical Details

### 1. **Frontend**
- Built with **Vue.js** for a modern and interactive user interface.

### 2. **Backend**
- Developed using **FastAPI**, providing robust API endpoints and seamless communication with the frontend.

### 3. **AI Models**
- **Whisper**: A fine-tuned `jlvdoorn` Whisper model for highly accurate ATC transcription, with customizable model sizes.
- **Llama 3.1**: A powerful language model for contextual understanding and SITREP generation, with customizable model sizes.

### 4. **Containerization**
- Entire application is encapsulated in **Docker containers** for portability and scalability.
- **Docker Compose**: Facilitates simplified setup and orchestration of services.

---

## Architecture Overview

```text
+---------------------+
|       Frontend      |
|    (Vue.js)         |
+---------------------+
          |
          v
+---------------------+
|       Backend       |
|    (FastAPI API)      |
+---------------------+
          |
          v
+---------------------+
|   AI Models         |
| - Whisper (ATC)     |
| - Llama 3.1 (LLM)   |
+---------------------+
          |
          v
+---------------------+
|   Docker Compose    |
| - Orchestration     |
| - Deployment        |
+---------------------+
```

---

## Installation

### Prerequisites
- **Docker** and **Docker Compose** installed on your system.

### Steps
Clone the repository:
   ```bash
   git clone https://github.com/amidstdebug/ATLAS.git
   cd atlas
   ```
Setup Python Environment
```bash
conda create -n atlas python
pip install librosa numpy soundfile torch transformers
conda activate atlas
python ./web-app/backend/misc/download_model.py
```
Install necessary applications:
```bash
   sudo apt update
   sudo apt install tmux docker
```
or if you're using Mac:
```bash
   brew update && brew upgrade
   brew install tmux docker
```
Mac users will also have to install the Docker for Mac application at:
1. [Apple Silicon](https://desktop.docker.com/mac/main/arm64/Docker.dmg?utm_source=docker&utm_medium=webreferral&utm_campaign=docs-driven-download-mac-arm64)
2. [Apple Intel](https://desktop.docker.com/mac/main/amd64/Docker.dmg?utm_source=docker&utm_medium=webreferral&utm_campaign=docs-driven-download-mac-amd64)

The vLLM service will automatically download the specified model when the Docker containers start.

Build and start the application:
```bash
./run_server_tmux.sh
```

Access the application:
   - Navigate to `http://localhost:7860` in your browser.

---

## Usage

1. **ATC Mode**:
   - Start live transcription of ATC communications.
   - View real-time SITREP updates.
   - Upload ATC communication files for transcription.

2. **Meeting Minutes**:
   - Start live recording of meeting discussions.
   - Upload recorded meetings for automated transcription.

3. **Model Customization**:
   - Choose the Llama 3.1 model size based on your system's performance capabilities.

---

## Contributing

We welcome contributions to improve ATLAS! To contribute:
1. Fork the repository.
2. Create a feature branch:
   ```bash
   git checkout -b feature-name
   ```
3. Commit your changes:
   ```bash
   git commit -m "Add feature description"
   ```
4. Push to the branch:
   ```bash
   git push origin feature-name
   ```
5. Open a pull request.

---

## License

This project is licensed under the Attribution-NonCommercial 4.0 International (CC BY-NC 4.0) license. 

This license allows others to share, adapt, and build upon the material as long as they credit the creator and do not use it for commercial purposes.

For detailed terms, please refer to the included `LICENSE` file.

---

## Acknowledgments

- **OpenAI's Whisper**: For its robust transcription capabilities.
- **Llama 3.1**: For its advanced language modeling.
- **Vue.js** and **FastAPI**: For providing the framework for frontend and backend development.
- **Docker**: For simplifying containerization and deployment.

---

## Contact

For questions or feedback, please open an issue or contact the maintainer at `work@jwong.dev`.

---
