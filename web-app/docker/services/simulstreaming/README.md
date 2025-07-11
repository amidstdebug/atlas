# SimulStreaming Service

This Docker image runs the [SimulStreaming](https://github.com/ufal/SimulStreaming) server which provides real time transcription over a TCP socket.

The container exposes port **43007** and uses the `simulstreaming_whisper_server.py` entrypoint with the large-v3 Whisper model by default.

The docker compose file mounts `./services/simulstreaming/models` from the host
to `/models` inside the container.  The server is configured with
`--model_path /models/large-v3.pt` so the downloaded model persists across
container restarts.
