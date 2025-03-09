import os
# import nvidia.cublas.lib
# import nvidia.cudnn.lib

# LD_LIBRARY_PATH = f'{os.path.dirname(nvidia.cublas.lib.__file__)}:{os.path.dirname(nvidia.cudnn.lib.__file__)}'

# os.environ["LD_LIBRARY_PATH"] = LD_LIBRARY_PATH

from .config import *
from .pipeline import OnlinePipeline
from .segments import TranscribedSegment
