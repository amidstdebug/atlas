# ./funcs/model.py
import torch
from transformers import AutoProcessor, AutoModelForSpeechSeq2Seq


def load_model(model_name_or_path):
	processor = AutoProcessor.from_pretrained(model_name_or_path)
	model = AutoModelForSpeechSeq2Seq.from_pretrained(model_name_or_path)
	device = torch.device("cuda:0" if torch.cuda.is_available() else "cpu")
	model.to(device)
	model.eval()
	return processor, model, device
