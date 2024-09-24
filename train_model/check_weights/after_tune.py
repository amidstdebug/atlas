import torch
from transformers import WhisperForConditionalGeneration

# Load the initial state_dict
initial_state_dict = torch.load("./models/initial_model_state.pth")

# Load the fine-tuned model
fine_tuned_model = WhisperForConditionalGeneration.from_pretrained("./models/distil_large_justin_retrained")
fine_tuned_state_dict = fine_tuned_model.state_dict()

# Compare the state_dicts
def compare_state_dicts(initial, fine_tuned):
    differences = {}
    for key in initial:
        if not torch.equal(initial[key], fine_tuned[key]):
            differences[key] = {
                "initial": initial[key],
                "fine_tuned": fine_tuned[key]
            }
    return differences

differences = compare_state_dicts(initial_state_dict, fine_tuned_state_dict)

if differences:
    print(f"Number of layers with changed weights: {len(differences)}")
    for layer in differences:
        print(f"Weights changed in layer: {layer}")
else:
    print("No differences found in the state dictionaries. Weights have not changed.")
