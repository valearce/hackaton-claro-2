import os
from pathlib import Path
import tempfile
import unittest

import numpy as np
import torch

from modelo.entorno.dispositivo import select_device
from modelo.perfiles import Autoencoder, evaluate


@unittest.skipUnless(os.environ.get("NBA_REQUIRE_CUDA") == "1", "Usa python -m modelo.probar para validar CUDA")
class GPUTests(unittest.TestCase):
    def test_backward_and_numpy_evaluation_use_gpu(self):
        device = select_device("cuda")
        model = Autoencoder(4, [8], 2).to(device)
        values = np.random.default_rng(3).normal(size=(64, 4)).astype(np.float32)
        tensor = torch.from_numpy(values).to(device)
        loss = ((model(tensor) - tensor) ** 2).mean()
        loss.backward()
        self.assertTrue(all(p.is_cuda and p.grad is not None and torch.isfinite(p.grad).all() for p in model.parameters()))
        mse, reconstruction = evaluate(model, values)
        self.assertEqual(reconstruction.shape, values.shape)
        self.assertTrue(np.isfinite(mse))

    def test_cuda_checkpoint_is_portable_to_cpu(self):
        model = Autoencoder(4, [8], 2).to(select_device("cuda"))
        values = np.random.default_rng(8).normal(size=(32, 4)).astype(np.float32)
        _, from_gpu = evaluate(model, values)
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "modelo.pt"
            torch.save(model.state_dict(), path)
            cpu = Autoencoder(4, [8], 2)
            cpu.load_state_dict(torch.load(path, map_location="cpu", weights_only=True))
            _, from_cpu = evaluate(cpu, values)
        np.testing.assert_allclose(from_gpu, from_cpu, atol=1e-5, rtol=1e-5)
