"""Autoencoder exploratorio con validación separada y referencia PCA."""
from copy import deepcopy
import json
from pathlib import Path
import random
import time

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.model_selection import train_test_split
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset
from ..entorno.dispositivo import select_device


class Preprocessor:
    """Transformaciones aprendidas únicamente en train y guardadas como JSON."""
    def __init__(self, config):
        self.config = config

    def raw(self, data):
        columns = self.config["numericas"] + self.config["binarias"]
        raw = data[columns].apply(pd.to_numeric, errors="raise").astype(float)
        for column in self.config["binarias"]:
            if not raw[column].dropna().isin([0, 1]).all():
                raise ValueError(f"La columna binaria {column} contiene otro valor")
        unlimited = self.config["plan_ilimitado"]
        mask = raw[unlimited["columna"]].eq(unlimited["valor"])
        raw["plan_ilimitado"] = mask.astype(float)
        raw.loc[mask, unlimited["columna"]] = np.nan
        for column in self.config["log1p"]:
            if (raw[column].dropna() < 0).any():
                raise ValueError(f"{column} no puede ser negativo para log1p")
            raw[column] = np.log1p(raw[column])
        if np.isinf(raw.to_numpy()).any():
            raise ValueError("El perfil contiene infinitos")
        return raw

    def matrix(self, data):
        raw = self.raw(data)
        for column, median in self.medians.items():
            raw[column] = raw[column].fillna(median)
        arrays = [raw.to_numpy(dtype=np.float32)]
        for column, categories in self.categories.items():
            values = data[column].fillna("").astype(str)
            arrays.extend([values.eq(category).to_numpy(dtype=np.float32)[:, None] for category in categories])
        return np.concatenate(arrays, axis=1)

    def fit(self, train):
        raw = self.raw(train)
        self.medians = {column: float(raw[column].median()) for column in raw}
        if not all(np.isfinite(list(self.medians.values()))):
            raise ValueError("Una variable no tiene valores de entrenamiento utilizables")
        self.categories = {column: sorted(train[column].fillna("").astype(str).unique().tolist()) for column in self.config["categoricas"]}
        self.features = list(raw.columns) + [f"{column}={category}" for column, values in self.categories.items() for category in values]
        encoded = self.matrix(train)
        self.mean = encoded.mean(axis=0, dtype=np.float64)
        self.scale = encoded.std(axis=0, dtype=np.float64)
        self.scale[self.scale < 1e-12] = 1
        return self

    def transform(self, data):
        return ((self.matrix(data) - self.mean) / self.scale).astype(np.float32)

    def to_dict(self):
        return {"config": self.config, "medianas": self.medians, "categorias": self.categories,
                "features": self.features, "media": self.mean.tolist(), "escala": self.scale.tolist()}

    @classmethod
    def from_dict(cls, saved):
        instance = cls(saved["config"])
        instance.medians, instance.categories = saved["medianas"], saved["categorias"]
        instance.features = saved["features"]
        instance.mean, instance.scale = np.array(saved["media"]), np.array(saved["escala"])
        return instance


class Autoencoder(nn.Module):
    def __init__(self, dimension, layers, latent):
        super().__init__()

        def network(sizes):
            modules = []
            for i, (before, after) in enumerate(zip(sizes, sizes[1:])):
                modules.append(nn.Linear(before, after))
                if i < len(sizes) - 2:
                    modules.append(nn.ReLU())
            return nn.Sequential(*modules)

        self.encoder = network([dimension, *layers, latent])
        self.decoder = network([latent, *reversed(layers), dimension])

    def forward(self, values):
        return self.decoder(self.encoder(values))


def evaluate(model, values):
    model.eval()
    with torch.no_grad():
        device = next(model.parameters()).device
        reconstructed = model(torch.from_numpy(values).to(device)).cpu().numpy()
    return float(np.mean((values - reconstructed) ** 2)), reconstructed


def run_profiles(data, config, directory, datos_sha256=None, dispositivo=None):
    from ..ejecutar import write_json
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    device = select_device(dispositivo)
    seed = config["semilla"]
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.set_num_threads(config["hilos_cpu"])
    torch.use_deterministic_algorithms(True)
    indexes = np.arange(len(data))
    train_count = round(len(data) * config["fraccion_train"])
    validation_count = round(len(data) * config["fraccion_validacion"])
    if min(train_count, validation_count, len(data) - train_count - validation_count) < 1:
        raise ValueError("Las particiones train, validación y test deben ser no vacías")
    train, temporary = train_test_split(indexes, train_size=train_count, random_state=seed)
    validation, test = train_test_split(temporary, train_size=validation_count, random_state=seed + 1)
    preprocessor = Preprocessor(config).fit(data.iloc[train])
    x = preprocessor.transform(data)
    if config["dimension_latente"] >= x.shape[1]:
        raise ValueError("La dimensión latente debe reducir las variables de entrada")
    model = Autoencoder(x.shape[1], config["capas"], config["dimension_latente"]).to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=config["learning_rate"], weight_decay=config["weight_decay"])
    generator = torch.Generator().manual_seed(seed)
    loader = DataLoader(TensorDataset(torch.from_numpy(x[train])), batch_size=config["batch_size"],
                        shuffle=True, num_workers=0, generator=generator)
    loss_function = nn.MSELoss()
    history = []
    best_loss, best_epoch, waiting, best = float("inf"), 0, 0, None
    print(f"Autoencoder {device}: {x.shape[1]} entradas -> {config['dimension_latente']} latentes; {len(train)} train", flush=True)
    for epoch in range(1, config["epocas"] + 1):
        model.train()
        total = 0.0
        for (batch,) in loader:
            batch = batch.to(device)
            optimizer.zero_grad(set_to_none=True)
            loss = loss_function(model(batch), batch)
            loss.backward()
            optimizer.step()
            total += loss.item() * len(batch)
        validation_loss, _ = evaluate(model, x[validation])
        history.append({"epoca": epoch, "mse_train": total / len(train), "mse_validacion": validation_loss})
        if validation_loss < best_loss - 1e-6:
            best_loss, best_epoch, best, waiting = validation_loss, epoch, deepcopy(model.state_dict()), 0
        else:
            waiting += 1
        if epoch == 1 or epoch % 5 == 0:
            print(json.dumps(history[-1]), flush=True)
        if waiting >= config["paciencia"]:
            break
    model.load_state_dict(best)
    test_loss, reconstructed_test = evaluate(model, x[test])
    with torch.no_grad():
        tensor = torch.from_numpy(x).to(device)
        latent = model.encoder(tensor).cpu().numpy()
        reconstructed = model(tensor).cpu().numpy()
    pca = PCA(n_components=config["dimension_latente"], random_state=seed).fit(x[train])
    pca_test = pca.inverse_transform(pca.transform(x[test]))
    pca_loss = float(np.mean((x[test] - pca_test) ** 2))
    clustering = KMeans(n_clusters=config["segmentos"], random_state=seed, n_init=10).fit(latent[train])
    labels = clustering.predict(latent)
    sample_size = min(config["muestra_silhouette"], len(test))
    silhouette = float(silhouette_score(latent[test], labels[test], sample_size=sample_size, random_state=seed)) if len(set(labels[test])) > 1 else None
    membership = np.full(len(data), "test", dtype=object)
    membership[train], membership[validation] = "train", "validacion"
    profiles = pd.DataFrame({"id_cliente": data.id_cliente.to_numpy(),
                             "segmento": [f"S{label + 1:02d}" for label in labels],
                             "particion": membership,
                             "error_reconstruccion": np.mean((x - reconstructed) ** 2, axis=1)})
    for dimension in range(latent.shape[1]):
        profiles[f"z{dimension + 1}"] = latent[:, dimension]
    profiles.to_csv(directory / "perfiles_clientes.csv", index=False)
    numeric = [c for c in data.select_dtypes(include="number").columns if c != "id_cliente"]
    summary = data[numeric].assign(segmento=profiles.segmento).groupby("segmento").mean()
    summary.insert(0, "clientes", profiles.groupby("segmento").size())
    summary.to_csv(directory / "resumen_segmentos.csv")
    pd.DataFrame(history).to_csv(directory / "historial_entrenamiento.csv", index=False)
    per_feature = dict(zip(preprocessor.features, np.mean((x[test] - reconstructed_test) ** 2, axis=0).astype(float).tolist()))
    metrics = {"objetivo": "reconstruccion_y_perfiles_exploratorios", "datos_sinteticos": True,
               "datos_sha256": datos_sha256,
               "train": len(train), "validacion": len(validation), "test": len(test),
               "dimension_entrada": x.shape[1], "dimension_latente": config["dimension_latente"],
               "mejor_epoca": best_epoch, "epocas_ejecutadas": len(history),
               "mse_test_autoencoder": test_loss, "mse_test_pca": pca_loss,
               "autoencoder_mejora_pca": bool(test_loss < pca_loss), "silhouette_test": silhouette,
               "mse_test_por_variable": per_feature, "segundos": time.perf_counter() - started,
               "torch": torch.__version__, "dispositivo": str(device),
               "gpu": torch.cuda.get_device_name(device) if device.type == "cuda" else None,
               "cuda_runtime": torch.version.cuda if device.type == "cuda" else None, "configuracion": config,
               "limite": "Los segmentos no predicen compras, emociones ni horarios. No sustituyen los scores oficiales."}
    write_json(directory / "metricas.json", metrics)
    write_json(directory / "preprocesamiento.json", preprocessor.to_dict())
    write_json(directory / "centros_segmentos.json", {"centros": clustering.cluster_centers_.tolist()})
    torch.save({"state_dict": model.state_dict(), "dimension": x.shape[1], "capas": config["capas"],
                "latentes": config["dimension_latente"]}, directory / "autoencoder.pt")
    np.savez(directory / "pca.npz", components=pca.components_, mean=pca.mean_)
    save_figures(history, test_loss, pca_loss, directory)
    print(json.dumps({"autoencoder_mse": test_loss, "pca_mse": pca_loss, "segundos": metrics["segundos"]}), flush=True)
    return metrics


def save_figures(history, autoencoder, pca, directory):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    frame = pd.DataFrame(history)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4), layout="constrained")
    axes[0].plot(frame.epoca, frame.mse_train, label="Entrenamiento", color="#DA291C")
    axes[0].plot(frame.epoca, frame.mse_validacion, label="Validación", color="#2563A6")
    axes[0].set(xlabel="Época", ylabel="Error cuadrático medio", title="Aprendizaje del autoencoder")
    axes[0].legend()
    bars = axes[1].bar(["Autoencoder", "PCA"], [autoencoder, pca], color=["#DA291C", "#64748B"])
    axes[1].bar_label(bars, fmt="%.4f")
    axes[1].set(ylabel="Error cuadrático medio en test", title="Mismas dimensiones latentes; menor es mejor")
    fig.savefig(directory / "comparacion_autoencoder_pca.png", dpi=160)
    plt.close(fig)


def infer_profiles(data, directory, dispositivo=None):
    """Aplica los artefactos locales sin volver a ajustar escalas ni entrenar."""
    directory = Path(directory)
    preprocessor = Preprocessor.from_dict(json.loads((directory / "preprocesamiento.json").read_text(encoding="utf-8")))
    saved = torch.load(directory / "autoencoder.pt", map_location="cpu", weights_only=True)
    model = Autoencoder(saved["dimension"], saved["capas"], saved["latentes"])
    model.load_state_dict(saved["state_dict"])
    device = select_device(dispositivo)
    model.to(device)
    model.eval()
    x = preprocessor.transform(data)
    with torch.no_grad():
        tensor = torch.from_numpy(x).to(device)
        latent = model.encoder(tensor).cpu().numpy()
        reconstructed = model(tensor).cpu().numpy()
    centers = np.array(json.loads((directory / "centros_segmentos.json").read_text())["centros"], dtype=latent.dtype)
    labels = np.argmin(np.sum((latent[:, None, :] - centers[None, :, :]) ** 2, axis=2), axis=1)
    return pd.DataFrame({"id_cliente": data.id_cliente.to_numpy(), "segmento": [f"S{label + 1:02d}" for label in labels],
                         "error_reconstruccion": np.mean((x - reconstructed) ** 2, axis=1)})
