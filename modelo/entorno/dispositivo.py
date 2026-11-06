"""Selección explícita del dispositivo del autoencoder, sin fallback oculto."""
import os

import torch


def select_device(requested=None):
    requested = requested or os.environ.get("NBA_DEVICE", "cpu")
    if requested not in ("cpu", "cuda"):
        raise ValueError("NBA_DEVICE/dispositivo debe ser cpu o cuda")
    if requested == "cuda":
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        if not torch.cuda.is_available():
            raise RuntimeError("Se solicitó CUDA, pero PyTorch no tiene una GPU disponible; no se sustituye por CPU")
        torch.backends.cudnn.benchmark = False
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
    return torch.device(requested)
