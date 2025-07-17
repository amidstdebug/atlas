# Environment Setup Guide

## Overview
This application uses environment variables to configure various services and settings. The setup has been streamlined to use a single `.env` file in the backend directory.

## Quick Setup

1. **Automatic Setup** (Recommended):
   ```bash
   cd backend
   python setup_env.py
   ```

2. **Manual Setup**:
   ```bash
   cd backend
   cp env.template .env
   # Edit .env with your preferred settings
   ```

## Environment Variables

### Application Settings
- `DEBUG`: Enable/disable debug mode (True/False)
- `PORT`: Backend API port (default: 5002)

### Service URLs
- `AUDIO_SERVER_URL`: Whisper service URL
- `VLLM_SERVER_URL`: vLLM service URL  
- `WHISPER_SERVICE_URL`: Whisper service URL
- `REDIS_URL`: Redis connection string

### Security Settings
- `JWT_SECRET`: Secret key for JWT tokens
- `JWT_ALGORITHM`: JWT algorithm (default: HS256)

### Model Settings
- `VLLM_MODEL`: vLLM model name (default: Qwen/Qwen3-0.6B)

### vLLM Service Configuration
- `VLLM_GPU_MEMORY_UTILIZATION`: GPU memory usage (0.0-1.0, default: 0.7)
- `VLLM_MAX_MODEL_LEN`: Maximum sequence length (default: 2048)
- `VLLM_TENSOR_PARALLEL_SIZE`: Number of GPUs (default: 1)

### CORS Settings
- `CORS_ORIGINS`: Allowed origins
- `CORS_ALLOW_CREDENTIALS`: Allow credentials
- `CORS_ALLOW_METHODS`: Allowed HTTP methods
- `CORS_ALLOW_HEADERS`: Allowed headers

## Troubleshooting

### vLLM Model Not Loading
If the vLLM model defaults to an empty string:
1. Ensure `.env` file exists in the backend directory
2. Check that `VLLM_MODEL` is set correctly
3. Restart Docker containers after changing environment variables

### GPU Memory Issues
If you encounter GPU memory errors:
1. Reduce `VLLM_GPU_MEMORY_UTILIZATION` (try 0.6 or 0.5)
2. Reduce `VLLM_MAX_MODEL_LEN` (try 1024)
3. Use a smaller model in `VLLM_MODEL`

### Service Connection Issues
If services can't connect:
1. Verify service URLs in `.env` match Docker service names
2. Check that all required services are running
3. Ensure network configuration is correct

## Development vs Production

### Development
- Use `DEBUG=True`
- Use localhost URLs for external services
- Use default model settings

### Production
- Set `DEBUG=False`
- Use secure JWT secrets
- Configure proper CORS origins
- Use production-ready model settings 