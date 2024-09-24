import torch
from transformers import WhisperForConditionalGeneration

# Initialize the model
model_name = "distil-whisper/distil-large-v3"
model = WhisperForConditionalGeneration.from_pretrained(model_name)

# Save the initial state_dict
initial_state_dict = model.state_dict()
torch.save(initial_state_dict, "./models/initial_model_state.pth")
