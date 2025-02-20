from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional, Iterator
from itertools import combinations

import time
import numpy as np
import torch
import torchaudio
import torch.nn.functional as F

from einops import rearrange

from scipy.optimize import linear_sum_assignment

from nemo.collections.asr.models.label_models import EncDecSpeakerLabelModel
from nemo.collections.asr.models.msdd_models import EncDecDiarLabelModel
from nemo.collections.asr.models.classification_models import EncDecClassificationModel
from nemo.collections.asr.parts.utils.online_clustering import OnlineSpeakerClustering
from nemo.collections.asr.parts.utils.offline_clustering import SpeakerClustering, getMultiScaleCosAffinityMatrix, getCosAffinityMatrix, getLaplacian
    
import matplotlib.pyplot as plt
import seaborn as sns

# device = 'cuda'

# marblenet_vad = EncDecClassificationModel.from_pretrained("vad_telephony_marblenet")
# msdd = EncDecDiarLabelModel.from_pretrained(model_name='diar_msdd_telephonic')
# msdd = msdd.eval()

# titanet_l = msdd.msdd._speaker_model