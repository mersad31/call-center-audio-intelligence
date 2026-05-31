# sentiment_model.py
from typing import List

import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from .config import settings


class SentimentModel:
    def __init__(self):
        self.tokenizer = AutoTokenizer.from_pretrained(
            settings.model_path, local_files_only=True
        )
        self.model = AutoModelForSequenceClassification.from_pretrained(
            settings.model_path, local_files_only=True
        )
        self.model.eval()

    def _label_from_id(self, idx: int) -> str:
        id2label = getattr(self.model.config, "id2label", None)
        if id2label and idx in id2label:
            label = id2label[idx].lower()
            if "neg" in label:
                return "negative"
            if "pos" in label:
                return "positive"
            if "neu" in label:
                return "neutral"
        if idx == 0:
            return "negative"
        if idx == 1:
            return "neutral"
        return "positive"

    @torch.no_grad()
    def predict(self, texts: List[str]) -> List[str]:
        if not texts:
            return []

        inputs = self.tokenizer(
            texts,
            padding=True,
            truncation=True,
            max_length=settings.max_length,
            return_tensors="pt",
        )
        outputs = self.model(**inputs)
        probs = torch.softmax(outputs.logits, dim=-1)
        preds = torch.argmax(probs, dim=-1).tolist()
        return [self._label_from_id(i) for i in preds]
