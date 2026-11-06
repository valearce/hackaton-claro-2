# Entorno estándar de pruebas del modelo

La suite se ejecuta en el Python del kernel Jupyter **`wsl_rtx5080`**, el entorno GPU registrado para los notebooks. El lanzador obtiene la distribución, usuario e intérprete desde su `kernel.json`; no contiene una ruta personal fija a la instalación.

Desde PowerShell, en la raíz:

```powershell
python -m modelo.probar
```

Para comprobar únicamente el entorno y ejecutar una operación CUDA con gradientes:

```powershell
python -m modelo.probar --solo-entorno
```

En Windows, este primer Python solo resuelve el kernel y lanza WSL con `CREATE_NO_WINDOW`. Las pruebas se ejecutan con el intérprete Linux del entorno GPU. No se abre otra terminal. Si WSL está bloqueado por el aislamiento de la herramienta de ejecución, ese comando necesita autorización para acceder al servicio WSL.

## Contrato verificado

[`config/entorno-pruebas.json`](../config/entorno-pruebas.json) fija Python 3.11 y las versiones de NumPy, pandas, SciPy, scikit-learn, Matplotlib, threadpoolctl y PyTorch. Se comprueba además el **runtime PyTorch `2.14.1+cu130` y CUDA `13.0`**, la GPU disponible y una multiplicación matricial con propagación de gradientes en CUDA.

La suite también valida OR-Tools 9.15.6755 desde la instalación local del módulo de grafo. Su preparación está en la [guía del optimizador](optimizador.md); no modifica el `protobuf` del entorno de notebooks.

El entorno detectado tiene Python 3.11.16 y una **NVIDIA GeForce RTX 5080 Laptop GPU**, capacidad de cómputo 12.0, soportada por el binario PyTorch mediante `sm_120`. Se reutilizaron las bibliotecas ya instaladas. TensorFlow 2.21.0 también está presente en ese entorno; la suite del proyecto usa PyTorch y no inicializa TensorFlow.

| Parte | Dónde calcula |
| --- | --- |
| Autoencoder e integración pequeña de entrenamiento | CUDA |
| Pruebas de gradientes y portabilidad de pesos | CUDA y comparación con CPU |
| Motor NBA / HiGHS | CPU dentro del mismo Python WSL |
| Preprocesamiento, PCA, KMeans, GMM e Isomap | CPU dentro del mismo Python WSL |

Las versiones incompatibles o CUDA no disponible producen un error. No hay sustitución silenciosa por CPU en la ejecución estándar. Una prueba omitida tampoco se considera una ejecución estándar aprobada.

La semilla es 42, se fijan cuatro hilos CPU y se usan algoritmos deterministas de PyTorch, `CUBLAS_WORKSPACE_CONFIG=:4096:8` y TF32 desactivado. La reproducibilidad no implica igualdad bit a bit entre CPU y GPU, arquitecturas o versiones; la comparación de inferencia CPU/CUDA usa tolerancias explícitas. Referencias primarias: [reproducibilidad de PyTorch](https://docs.pytorch.org/docs/stable/notes/randomness.html), [cuBLAS](https://docs.nvidia.com/cuda/cublas/#results-reproducibility) y [comandos WSL](https://learn.microsoft.com/en-us/windows/wsl/basic-commands).

## Evidencia y resultados

Cada ejecución guarda en `resultados/pruebas-gpu/`:

- `metricas.json`: resultado de la suite, versiones, intérprete, GPU, conteo de pruebas, omisiones y huellas de código/datos.
- `pruebas.log`: nombres y resultados de las pruebas.
- `entorno.json`: comprobación independiente creada por `--solo-entorno`, sin reemplazar el resultado de la suite.

La suite incluye el caso integral pequeño que entrena el autoencoder en CUDA, compara los cuatro pipelines sobre la misma partición test y comprueba la recarga de sus pesos para inferencia en CPU. No vuelve a entrenar los 100.000 clientes ni cambia la evaluación histórica por ejecutar tests.

## Entrenamiento y comprobaciones CPU

Dentro del Python GPU de WSL, con el repositorio como directorio actual:

```bash
python -m modelo.probar --directo
python -m modelo.ejecutar --tarea perfiles --dispositivo cuda --fecha 2026-11-05
python -m modelo.comparar
```

El segundo comando realiza un entrenamiento completo; se ejecuta cuando se quiere generar otra evaluación. `--dispositivo cpu` permite una ejecución de referencia en el mismo entorno. También se admite `NBA_DEVICE=cuda` para los perfiles.

Para una comprobación CPU fuera del entorno estándar se conserva:

```powershell
python -m unittest discover -s modelo/tests -v
```

En esa modalidad se omiten las dos pruebas que exigen CUDA, y el resultado no sustituye la validación GPU estándar. Los resultados publicados anteriormente de autoencoder/PCA/GMM/Isomap fueron calculados en CPU y siguen identificados como tales.
