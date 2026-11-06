# Entorno de ejecución del motor

El motor NBA usa el Python WSL registrado en el kernel Jupyter `wsl_rtx5080`. El lanzador obtiene distribución, usuario e intérprete de su `kernel.json`; no fija una ruta personal. [config/entorno.json](../config/entorno.json) indica el kernel y los hilos CPU.

Desde PowerShell, en la raíz:

```powershell
python -m modelo.ejecutar --fecha 2026-11-05
```

Windows lanza WSL con `CREATE_NO_WINDOW`. Dentro de WSL se puede ejecutar el mismo comando con el Python del entorno. OR-Tools calcula en CPU y esta tarea no inicializa PyTorch ni CUDA. El acceso al servicio WSL puede requerir autorización del entorno de ejecución.

## Preparar OR-Tools

El entorno existente tiene `protobuf 7.36.1`, fuera del intervalo declarado por el paquete completo de OR-Tools. Se usa únicamente la extensión nativa `ortools.graph.python.min_cost_flow`, instalada en una carpeta local sin sus dependencias Python. Desde el Python WSL seleccionado, en la raíz del repositorio:

```bash
python -m pip install --no-deps --only-binary=:all: --no-cache-dir \
  --target .local/python/ortools-linux -r modelo/requirements-flujo.txt
```

Se exige la versión **9.15.6755**. En Linux, si existe la carpeta local, se comprueba que el módulo proceda de ella. Esta instalación está limitada al grafo de flujo; otras funcionalidades del paquete requieren revisar sus dependencias. Se conserva el `protobuf` de los notebooks.

La consola web usa un entorno independiente: Python 3.11 local en Windows y Python 3.12 en Vercel, con las dependencias de [backend/requirements.txt](../../backend/requirements.txt). En esos entornos se instala el paquete completo y el cargador utiliza la extensión nativa de la plataforma. Una carpeta con binarios Linux no se carga en Windows. Consulta la [guía de la API](../../backend/README.md) para iniciar Next.js y FastAPI.

El motor requiere NumPy y pandas del entorno existente. `requirements.txt` conserva las bibliotecas científicas utilizadas por los perfiles. No se instalan dependencias en cada ejecución y no hay sustitución automática por LP.

## Perfiles de consumo

El entrenamiento opcional de perfiles usa PyTorch. Para CUDA, el entorno existente dispone de PyTorch `2.14.1+cu130`, CUDA 13.0 y una NVIDIA GeForce RTX 5080 Laptop GPU. La selección explícita `--dispositivo cuda` produce un error si CUDA no está disponible; `--dispositivo cpu` permite entrenamiento en CPU.

La suite de pruebas y sus lanzadores fueron retirados. La operación NBA conserva sus controles de datos, auditoría de negocio y certificado exacto en cada corrida. Consulta la [guía del motor](optimizador.md).
