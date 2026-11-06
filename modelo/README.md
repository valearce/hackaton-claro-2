# Motor NBA con flujo de coste mínimo

El motor elige productos y un canal por cliente mediante **OR-Tools**, con los scores del reto, reglas de elegibilidad, permisos y capacidades. Es el único optimizador de la ejecución normal. Cada parrilla exige un certificado primal-dual entero con brecha exacta cero y una auditoría de reglas sin violaciones.

## Ejecutar

Desde la raíz, en PowerShell:

```powershell
python -m modelo.ejecutar --fecha 2026-11-05
python -m modelo.exportar_evaluacion
```

La tarea predeterminada es `nba`. El lanzador reutiliza el Python WSL del kernel `wsl_rtx5080`, sin abrir terminales. El flujo calcula en CPU; no necesita inicializar CUDA. La preparación de OR-Tools está en [docs/entorno.md](docs/entorno.md).

`--datos RUTA`, `--config CARPETA` y `--salida CARPETA` permiten elegir las entradas y el destino. La fecha controla la vigencia de las campañas. El CSV se lee como texto para conservar los decimales originales y los identificadores.

La ejecución guarda en `resultados/nba/`:

- `parrilla_optimo.csv`: una fila por cliente, canal, campañas y explicación.
- `certificado.json.gz`: multiplicadores enteros ligados a datos, configuración y fecha.
- `metricas.json`: valor exacto, cupos, controles, certificado, tiempos y huellas de código.

`resultados/` está excluido de Git. La exportación actualiza [evaluacion/nba.json](evaluacion/nba.json) únicamente si coinciden los datos, configuración y código y el resultado está certificado sin violaciones.

## Resultado NBA

Sobre los 100.000 clientes de [datos/clientes.csv](../datos/clientes.csv), fecha 2026-11-05:

| Métrica | Motor OR-Tools |
| --- | ---: |
| Valor esperado exacto | 10.940,0024511 |
| Clientes con acción | 60.422 |
| Productos asignados | 76.841 |
| Violaciones | 0 |
| Brecha exacta | 0 |

Frente a la referencia publicada de 10.241,5, el incremento es **698,5024511 (+6,82 %)**. Son valores sobre scores sintéticos, no ventas observadas. La [guía del optimizador](docs/optimizador.md) explica el certificado y el alcance.

## Organización

| Carpeta | Responsabilidad |
| --- | --- |
| `nba/` | Motor único y auditoría independiente de reglas |
| `optimizacion/` | Problema decimal exacto, flujo OR-Tools y certificados |
| `entorno/` | Lanzador WSL y selección de dispositivo para perfiles |
| `config/` | Campañas, reglas, parámetros y entorno |
| `docs/` | Guías de ejecución y optimización |
| `kit_original/` | CSV oficiales sin modificar |
| `evaluacion/` | Métricas actuales del motor e informes históricos |
| `perfiles/` | Entrenamiento e inferencia de perfiles, independientes de la asignación NBA |
| `resultados/` | Parrillas, pesos y registros locales |

Se retiraron la suite de pruebas, los comparadores ejecutables, el LP y la baseline. Los [resultados históricos LP/flujo](evaluacion/optimizador.json) y [perfiles PCA/GMM/Isomap/autoencoder](evaluacion/comparacion.json) conservan las mediciones y configuraciones originales; no describen corridas del código actual.

## Configuración y alcance

`campanas.json`, `reglas.json` y `parametros.json` determinan las ofertas, exclusiones, umbrales y capacidades. El backend es `flujo_ortools`, el objetivo es `valor_esperado` y el modo admitido es `ponderado`. Se rechazan otros backends u objetivos. Las [reglas](../REGLAS.md) documentan las 45 variables y los controles R01–R16.

El objetivo es `score_producto × score_canal × valor_negocio`, sumado sobre los productos asignados. Se admite un canal y hasta dos productos distintos por contacto; dos productos consumen un solo cupo de canal. Los pesos de prioridad no alteran ese objetivo. La jerarquía se informa como indicador.

Los perfiles guardados se pueden volver a entrenar de forma independiente con `python -m modelo.ejecutar --tarea perfiles --dispositivo cuda --fecha 2026-11-05`. No modifican los scores ni participan en la optimización NBA. Se conservan sus pesos locales; los notebooks no se incluyen.
