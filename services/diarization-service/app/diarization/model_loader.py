import os
os.environ["SPEECHBRAIN_DISABLE_NLP"] = "1"
os.environ["SPEECHBRAIN_DISABLE_K2"] = "1"

import torch
from pyannote.audio import Pipeline
from app.logger import setup_logger
from dotenv import load_dotenv


logger = setup_logger("model_loader")
load_dotenv()

PYANNOTE_MODEL = "pyannote/speaker-diarization-3.1"
_pipeline = None


def load_diarization_model():
    global _pipeline

    if _pipeline is not None:
        logger.info("Diarization model already loaded, using cached version")
        return _pipeline

    hf_token = os.getenv("HF_TOKEN")
    if not hf_token:
        raise EnvironmentError("HF_TOKEN environment variable is required for pyannote models")

    logger.info(f"Loading diarization model: {PYANNOTE_MODEL}")

    try:
        _pipeline = Pipeline.from_pretrained(PYANNOTE_MODEL, use_auth_token=hf_token)

        if torch.cuda.is_available():
            _pipeline = _pipeline.to(torch.device("cuda"))
            mem_gb = torch.cuda.memory_allocated() / 1e9
            logger.info(f"Diarization model on GPU | memory used: {mem_gb:.2f} GB")
        else:
            logger.info("Diarization model on CPU")

        return _pipeline

    except Exception as e:
        logger.error(f"Failed to load diarization model: {e}", exc_info=True)
        raise


def get_diarization_pipeline():
    if _pipeline is None:
        load_diarization_model()
    return _pipeline
