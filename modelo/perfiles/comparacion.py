"""Comparación fuera de muestra: PCA, autoencoder, mezclas gaussianas e Isomap.

Reutiliza exactamente las particiones y el preprocesamiento del autoencoder.
Selecciona hiperparámetros en validación y consulta test una sola vez al final.
"""
import argparse
import hashlib
import json
from pathlib import Path
import time
import warnings

import numpy as np
import pandas as pd
import sklearn
from sklearn.cluster import KMeans
from sklearn.manifold import Isomap, trustworthiness
from sklearn.metrics import (calinski_harabasz_score, davies_bouldin_score,
                             silhouette_score)
from sklearn.mixture import GaussianMixture
from sklearn.neighbors import KNeighborsRegressor
from threadpoolctl import threadpool_limits
import torch

from ..ejecutar import write_json
from .autoencoder import Autoencoder, Preprocessor
from ..rutas import DATOS, MODELO


def row_errors(actual, predicted):
    return np.mean((actual.astype(np.float64) - predicted) ** 2, axis=1)


def improvement(reference, candidate):
    """Porcentaje de reducción de error; negativo significa empeoramiento."""
    return float(100 * (1 - np.mean(candidate) / np.mean(reference)))


def paired_interval(reference, candidate, repeats=500, seed=42):
    """IC bootstrap de la diferencia MSE candidato menos referencia, por cliente."""
    difference = np.asarray(candidate) - np.asarray(reference)
    rng = np.random.default_rng(seed)
    means = np.array([rng.choice(difference, len(difference), replace=True).mean()
                      for _ in range(repeats)])
    return {"diferencia_mse": float(difference.mean()),
            "ic95": np.quantile(means, [.025, .975]).tolist(),
            "unidad_remuestreo": "cliente_test", "repeticiones": repeats}


def transform_batches(model, values, size):
    return np.concatenate([model.transform(values[start:start + size])
                           for start in range(0, len(values), size)])


def cluster_quality(x, labels):
    count = len(np.unique(labels))
    if count < 2 or count >= len(x):
        return {"silhouette_original": None, "davies_bouldin_original": None,
                "calinski_harabasz_original": None, "grupos_observados": count}
    return {"silhouette_original": float(silhouette_score(x, labels)),
            "davies_bouldin_original": float(davies_bouldin_score(x, labels)),
            "calinski_harabasz_original": float(calinski_harabasz_score(x, labels)),
            "grupos_observados": count}


def load_reference(data, directory):
    """Falla si se mezclan artefactos, clientes o un preprocesamiento incompatible."""
    directory = Path(directory)
    metadata = json.loads((directory / "metricas.json").read_text(encoding="utf-8"))
    saved_pre = json.loads((directory / "preprocesamiento.json").read_text(encoding="utf-8"))
    preprocessor = Preprocessor.from_dict(saved_pre)
    if saved_pre["config"] != metadata["configuracion"]:
        raise ValueError("Configuración del modelo y preprocesamiento diferentes")
    profiles = pd.read_csv(directory / "perfiles_clientes.csv")
    if not np.array_equal(profiles.id_cliente.to_numpy(), data.id_cliente.to_numpy()):
        raise ValueError("Los clientes o su orden no coinciden con los artefactos")
    partitions = {name: np.flatnonzero(profiles.particion.eq(name).to_numpy())
                  for name in ("train", "validacion", "test")}
    if sum(map(len, partitions.values())) != len(data) or any(len(v) == 0 for v in partitions.values()):
        raise ValueError("Particiones incompletas")
    # Reajustar solo el preprocesador comprueba que no se cambiaron los datos.
    fitted = Preprocessor(preprocessor.config).fit(data.iloc[partitions["train"]])
    structure_matches = (fitted.config == preprocessor.config and fitted.categories == preprocessor.categories
                         and fitted.features == preprocessor.features and fitted.medians == preprocessor.medians)
    # El CSV conserva membresía, no el orden aleatorio interno de train; las
    # reducciones flotantes pueden variar en sus últimos bits al reordenarlo.
    statistics_match = (np.allclose(fitted.mean, preprocessor.mean, atol=1e-10, rtol=1e-10)
                        and np.allclose(fitted.scale, preprocessor.scale, atol=1e-10, rtol=1e-10))
    if not (structure_matches and statistics_match):
        raise ValueError("El conjunto train cambió desde el entrenamiento original")
    x = preprocessor.transform(data)
    saved = torch.load(directory / "autoencoder.pt", map_location="cpu", weights_only=True)
    model = Autoencoder(saved["dimension"], saved["capas"], saved["latentes"])
    model.load_state_dict(saved["state_dict"])
    model.eval()
    with torch.no_grad():
        latent = model.encoder(torch.from_numpy(x)).numpy()
        reconstruction = model(torch.from_numpy(x)).numpy()
    stored_latent = profiles[[f"z{i + 1}" for i in range(saved["latentes"])]].to_numpy()
    if not np.allclose(latent, stored_latent, atol=1e-5, rtol=1e-5):
        raise ValueError("Datos/modelo no reproducen los latentes almacenados")
    if not np.allclose(row_errors(x, reconstruction), profiles.error_reconstruccion, atol=1e-5, rtol=1e-5):
        raise ValueError("Datos/modelo no reproducen los errores almacenados")
    return x, partitions, profiles, latent, reconstruction, metadata


def run_comparison(data, config, profiles_directory, directory, data_path):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    seed = config["semilla"]
    np.random.seed(seed)  # ARPACK dentro de KernelPCA/Isomap también usa el RNG global.
    torch.set_num_threads(config["hilos_cpu"])
    with threadpool_limits(limits=config["hilos_cpu"]):
        x, partitions, profiles, ae_z, ae_rec, previous = load_reference(data, profiles_directory)
        train, validation, test = (partitions[c] for c in ("train", "validacion", "test"))
        dimension = config["dimension_latente"]
        if dimension != ae_z.shape[1]:
            raise ValueError("La dimensión debe coincidir con autoencoder y PCA guardados")
        rng = np.random.default_rng(seed)
        sample = rng.choice(len(test), min(config["muestra_calidad"], len(test)), replace=False)
        neighbors_sample = sample[:min(config["muestra_vecinos"], len(sample))]
        models = {}
        rows = []
        selection = {"gmm": [], "isomap": []}
        saved_pca = np.load(Path(profiles_directory) / "pca.npz")
        pca_z = (x - saved_pca["mean"]) @ saved_pca["components"].T
        pca_rec = pca_z @ saved_pca["components"] + saved_pca["mean"]
        for name, z, rec in (("PCA + KMeans", pca_z, pca_rec), ("Autoencoder + KMeans", ae_z, ae_rec)):
            tick = time.perf_counter()
            if name.startswith("Autoencoder"):
                labels = profiles.segmento.to_numpy()
            else:
                clustering = KMeans(n_clusters=config["segmentos"], n_init=10, random_state=seed).fit(z[train])
                labels = clustering.predict(z[test])
            models[name] = {"z_test": z[test], "labels": labels[test] if len(labels) == len(data) else labels,
                            "errors": row_errors(x[test], rec[test]),
                            "mse_validacion": float(row_errors(x[validation], rec[validation]).mean()),
                            "segundos_ajuste": None, "segundos_auxiliares": time.perf_counter() - tick,
                            "artefacto_reutilizado": True}

        # Densidad fuera de muestra elige la covarianza del GMM; no se usa test.
        best_gmm, best_score = None, -np.inf
        for covariance in config["gmm"]["covarianzas"]:
            tick = time.perf_counter()
            gmm = GaussianMixture(n_components=config["segmentos"], covariance_type=covariance,
                                  n_init=config["gmm"]["n_init"], max_iter=config["gmm"]["max_iter"],
                                  reg_covar=config["gmm"]["reg_covar"], random_state=seed)
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                gmm.fit(x[train])
            score = float(gmm.score(x[validation]))
            validation_rec = gmm.predict_proba(x[validation]) @ gmm.means_
            candidate = {"covarianza": covariance, "log_verosimilitud_validacion": score,
                         "bic_train": float(gmm.bic(x[train])), "convergio": bool(gmm.converged_),
                         "iteraciones": int(gmm.n_iter_),
                         "mse_validacion": float(row_errors(x[validation], validation_rec).mean()),
                         "segundos": time.perf_counter() - tick,
                         "avisos": [str(w.message) for w in caught]}
            selection["gmm"].append(candidate)
            print(json.dumps({"GMM": candidate}, ensure_ascii=False), flush=True)
            if gmm.converged_ and score > best_score:
                best_gmm, best_score = gmm, score
        if best_gmm is None:
            raise RuntimeError("Ninguna mezcla gaussiana convergió; revisar candidatos")
        gmm_z = best_gmm.predict_proba(x[test])
        selected_gmm = next(v for v in selection["gmm"] if v["covarianza"] == best_gmm.covariance_type)
        models["Mezcla gaussiana"] = {"z_test": gmm_z, "labels": best_gmm.predict(x[test]),
            "errors": row_errors(x[test], gmm_z @ best_gmm.means_),
            "mse_validacion": selected_gmm["mse_validacion"],
            "segundos_ajuste": selected_gmm["segundos"], "artefacto_reutilizado": False,
            "log_verosimilitud_test": float(best_gmm.score(x[test])),
            "covarianza": best_gmm.covariance_type,
            "representacion": "5 probabilidades de pertenencia (suman 1; 4 grados de libertad)"}

        # Isomap necesita distancias entre todos sus puntos de ajuste: N².
        landmark_indexes = rng.choice(train, min(config["isomap"]["puntos_entrenamiento"], len(train)), replace=False)
        best_isomap, best_decoder, best_mse, best_z_train = None, None, np.inf, None
        best_iso_metadata = None
        for neighbors in config["isomap"]["vecinos"]:
            tick = time.perf_counter()
            isomap = Isomap(n_components=dimension, n_neighbors=neighbors, n_jobs=1,
                            eigen_solver="arpack", path_method="D", neighbors_algorithm="brute")
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                isomap.fit(x[landmark_indexes])
            z_train = transform_batches(isomap, x[train], config["isomap"]["batch_size"])
            z_validation = transform_batches(isomap, x[validation], config["isomap"]["batch_size"])
            isomap_seconds = time.perf_counter() - tick
            for decoder_neighbors in config["isomap"]["vecinos_decoder"]:
                decoder_tick = time.perf_counter()
                decoder = KNeighborsRegressor(n_neighbors=decoder_neighbors, weights="distance", n_jobs=1).fit(z_train, x[train])
                mse = float(row_errors(x[validation], decoder.predict(z_validation)).mean())
                candidate = {"vecinos_grafo": neighbors, "vecinos_decoder": decoder_neighbors,
                             "puntos_grafo_train": len(landmark_indexes), "puntos_decoder_train": len(train),
                             "mse_validacion": mse, "segundos_isomap": isomap_seconds,
                             "segundos_decoder": time.perf_counter() - decoder_tick,
                             "avisos": [str(w.message) for w in caught]}
                selection["isomap"].append(candidate)
                print(json.dumps({"Isomap": candidate}, ensure_ascii=False), flush=True)
                if mse < best_mse:
                    best_isomap, best_decoder, best_mse, best_z_train = isomap, decoder, mse, z_train
                    best_iso_metadata = candidate
        tick = time.perf_counter()
        iso_test = transform_batches(best_isomap, x[test], config["isomap"]["batch_size"])
        iso_prediction = best_decoder.predict(iso_test)
        iso_clustering = KMeans(n_clusters=config["segmentos"], n_init=10, random_state=seed).fit(best_z_train)
        models["Isomap + kNN + KMeans"] = {"z_test": iso_test, "labels": iso_clustering.predict(iso_test),
            "errors": row_errors(x[test], iso_prediction), "mse_validacion": best_mse,
            "segundos_ajuste": best_iso_metadata["segundos_isomap"] + best_iso_metadata["segundos_decoder"],
            "segundos_transformacion_test_y_cluster": time.perf_counter() - tick,
            "artefacto_reutilizado": False, **{k: v for k, v in best_iso_metadata.items() if k not in ("mse_validacion",)}}

        reference_errors = models["Autoencoder + KMeans"]["errors"]
        pca_errors = models["PCA + KMeans"]["errors"]
        error_table = pd.DataFrame({"id_cliente": data.iloc[test].id_cliente.to_numpy()})
        for number, (name, item) in enumerate(models.items(), start=1):
            errors = item.pop("errors")
            latent, labels = item.pop("z_test"), item.pop("labels")
            error_table[f"mse_{number}"] = errors
            error_table[f"grupo_{number}"] = labels
            metrics = {"metodo": name, "mse_test": float(errors.mean()), **item,
                       "reduccion_mse_vs_pca_pct": improvement(pca_errors, errors),
                       "reduccion_mse_vs_autoencoder_pct": improvement(reference_errors, errors),
                       **cluster_quality(x[test][sample], labels[sample]),
                       "trustworthiness_test": float(trustworthiness(x[test][neighbors_sample], latent[neighbors_sample],
                                                                               n_neighbors=config["vecinos_calidad"])),
                       "comparacion_pareada_autoencoder": paired_interval(reference_errors, errors, config["bootstrap_repeticiones"], seed)}
            rows.append(metrics)
            print(json.dumps({"resultado": metrics}, ensure_ascii=False), flush=True)
        reports = {"datos_sha256": hashlib.sha256(Path(data_path).read_bytes()).hexdigest(),
                   "particiones": {k: len(v) for k, v in partitions.items()},
                   "dimension_entrada": x.shape[1], "dimension_latente": dimension,
                   "configuracion": config, "seleccion_solo_validacion": selection,
                   "criterio_gmm": "Máxima log-verosimilitud de validación entre modelos convergidos",
                   "criterio_isomap": "Mínimo MSE de validación del pipeline Isomap + decoder kNN",
                   "muestra_calidad": len(sample), "muestra_vecinos": len(neighbors_sample),
                   "espacio_calidad_grupos": "20 variables preprocesadas originales, misma muestra test para todos",
                   "resultados": rows, "segundos_experimento": time.perf_counter() - started,
                   "columnas_errores_test": {str(i): row["metodo"] for i, row in enumerate(rows, start=1)},
                   "sklearn": sklearn.__version__, "referencia_autoencoder": previous,
                   "limites": ["No hay etiquetas de conversión; estas métricas no miden incremento de ventas.",
                               "GMM reconstruye con medias ponderadas; Isomap usa un decodificador kNN adicional.",
                               "Isomap ajusta el grafo en una muestra train y extiende a clientes fuera de muestra.",
                               "Tiempos de referencias reutilizadas no son tiempos nuevos de entrenamiento.",
                               "Un IC bootstrap en datos sintéticos no garantiza generalización a clientes reales.",
                               "HNSW fue investigado, no se incorporó a esta prueba de vecinos exactos."]}
        write_json(directory / "metricas.json", reports)
        pd.DataFrame([{k: v for k, v in row.items() if not isinstance(v, (list, dict))} for row in rows]).to_csv(directory / "comparacion.csv", index=False)
        pd.DataFrame({"id_cliente": data.iloc[test].id_cliente.to_numpy(),
                      "muestra_calidad": np.isin(np.arange(len(test)), sample)}).to_csv(directory / "clientes_test.csv", index=False)
        error_table.to_csv(directory / "errores_test.csv", index=False)
        save_figures(rows, directory)
        return reports


def save_figures(rows, directory):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = ["PCA", "Autoencoder", "GMM", "Isomap + kNN"]
    colors = ["#64748B", "#DA291C", "#2563A6", "#0F766E"]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), layout="constrained")
    for ax, metric, title in zip(axes, ["mse_test", "silhouette_original", "trustworthiness_test"],
                                ["Reconstrucción en test\nMenor es mejor", "Silhouette en variables originales\nMayor es mejor", "Conservación de vecinos (trustworthiness)\nMayor es mejor"]):
        bars = ax.bar(labels, [r[metric] for r in rows], color=colors)
        ax.bar_label(bars, fmt="%.3f", padding=3)
        ax.set_title(title, fontsize=11)
        ax.tick_params(axis="x", labelrotation=20)
        ax.margins(y=.15)
    axes[2].set_ylim(0, 1.12)
    fig.savefig(directory / "comparacion_metodos.png", dpi=160)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--datos", type=Path, default=DATOS)
    parser.add_argument("--config", type=Path, default=MODELO / "config/comparacion.json")
    parser.add_argument("--perfiles", type=Path, default=MODELO / "resultados/perfiles")
    parser.add_argument("--salida", type=Path, default=MODELO / "resultados/comparacion")
    args = parser.parse_args()
    run_comparison(pd.read_csv(args.datos, keep_default_na=False), json.loads(args.config.read_text(encoding="utf-8-sig")),
                   args.perfiles, args.salida, args.datos)


if __name__ == "__main__":
    main()
