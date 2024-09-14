import os

def create_directory_structure(base_dir):
    dirs = [
        os.path.join(base_dir, "data/train"),
        os.path.join(base_dir, "data/validation"),
        os.path.join(base_dir, "transcriptions/train"),
        os.path.join(base_dir, "transcriptions/validation"),
        os.path.join(base_dir, "logs/tensorboard"),
        os.path.join(base_dir, "models/output")
    ]

    for directory in dirs:
        if not os.path.exists(directory):
            os.makedirs(directory)
            print(f"Directory created: {directory}")
        else:
            print(f"Directory already exists: {directory}")

if __name__ == "__main__":
    # Get the directory where the Python script is located
    base_dir = os.path.dirname(os.path.abspath(__file__))
    create_directory_structure(base_dir)
