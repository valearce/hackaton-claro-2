# Optimizador exacto: LP, flujo y certificados

Esta implementación compara dos formas de resolver la misma asignación: LP con HiGHS y flujo de coste mínimo con OR-Tools. La construcción independiente de alternativas y el verificador del certificado usan los decimales originales, sin redondear scores.

## Resultado medido

Con los 100.000 clientes, fecha de negocio 2026-11-05 y tres repeticiones por backend en el entorno estándar:

| Métrica | LP / HiGHS | Flujo / OR-Tools |
| --- | ---: | ---: |
| Valor esperado exacto | 10.940,0024511 | 10.940,0024511 |
| Brecha exacta | 0 | 0 |
| Violaciones del auditor | 0 | 0 |
| Mediana de solución | 8,546 s | 0,164 s |
| Mediana del backend, con preparación y parrilla | 8,694 s | 0,319 s |
| Mediana del RSS pico del trabajador | 332,92 MiB | 220,73 MiB |

El flujo reduce el tiempo del solver **52,1 veces** y el del backend **27,2 veces**. Al incorporar la preparación exacta común y la certificación, la aceleración estimada es **3,75 veces**; esa estimación no incluye el arranque de Python, el preflight CUDA ni la escritura de artefactos. El valor óptimo se conserva: esta mejora es de rendimiento y comprobación independiente.

Los [resultados completos y las huellas de código/datos](../evaluacion/optimizador.json) registran cada repetición, las fases y sus límites. El certificado se volvió a verificar desde el CSV original con el comando independiente, sin ejecutar ningún solver. La exportación con `python -m modelo.exportar_evaluacion` exige que los datos, configuración y código sigan coincidiendo y que no haya brecha ni violaciones.

## Ejecutar en el entorno estándar

Desde la raíz, en Windows:

```powershell
python -m modelo.probar
python -m modelo.benchmark_optimizador --repeticiones 3
```

El segundo comando resuelve ambos backends en procesos nuevos del Python del kernel WSL registrado. Alterna su orden entre repeticiones. El [contrato de entorno](entorno.md) fija las bibliotecas y comprueba CUDA; estos dos solvers calculan en CPU.

Para generar únicamente una asignación por flujo y su certificado:

```powershell
python -m modelo.benchmark_optimizador --backend flujo --repeticiones 1
```

Las primeras parrillas completas y certificados comprimidos de cada backend y las mediciones de todas las repeticiones están en `resultados/optimizador/`, excluido de Git. Cada repetición tiene su carpeta (`lp-1`, `flujo-1`, etc.). `metricas.json` contiene las medianas y los resultados de auditoría. El archivo intermedio y las parrillas/certificados repetidos se retiran al terminar. Los informes compactos revisados se conservan en `evaluacion/`.

## Dependencia de flujo aislada

El entorno existente tiene `protobuf 7.36.1`; OR-Tools declara un intervalo diferente para el paquete completo. Para esta implementación se usa **solo su extensión nativa de grafo**, desde una carpeta local, sin instalar sus dependencias ni importar CP-SAT o los módulos Python de protobuf.

Dentro del Python GPU de WSL, desde la raíz del proyecto:

```bash
python -m pip install --no-deps --only-binary=:all: --no-cache-dir \
  --target .local/python/ortools-linux -r modelo/requirements-flujo.txt
```

El módulo local y su versión se verifican mediante una operación de flujo durante el preflight. La comprobación fija OR-Tools 9.15.6755 y rechaza cargar otra copia accidental. Esta preparación **no constituye una instalación compatible del conjunto completo de OR-Tools**: otras funcionalidades requieren revisar sus dependencias y su entorno. El código de flujo no cambia el `protobuf` de los notebooks.

## Construcción independiente del problema

`optimizacion/problema.py` vuelve a leer el CSV original como texto, interpreta sus números como decimales finitos y evalúa reglas por su propia implementación. No recibe máscaras ni paquetes elegidos por `Engine`.

Para cada cliente y canal enumera todos los paquetes permitidos de uno y dos productos distintos, incluyendo campañas activas/vigentes, elegibilidad, permisos, umbrales y política de contacto. Conserva el de mayor aporte exacto. Esto es suficiente para el objetivo aditivo actual: no hay cupos globales por producto ni otras restricciones que acoplen el contenido de los paquetes entre clientes.

Los valores se convierten a enteros mediante una potencia de diez común. Con el CSV inicial se usa denominador **1.000.000.000**. Se comprueba que la conversión sea exacta y que los costes y sus sumas entren en los rangos numéricos de los backends. Una precisión excesiva produce un error; no se modifica el score para resolverla. El flujo puede dividir todos sus costes por su máximo común divisor: esa transformación es exacta y no cambia su orden.

Antes del benchmark se comparan todas las máscaras y todos los máximos cliente-canal con el motor anterior. Si difieren, se interrumpe la comparación para investigar la interpretación.

## Red de flujo

```mermaid
flowchart LR
    F[Fuente: N unidades] -->|capacidad 1| C[Cliente]
    C -->|capacidad 1; coste = menos valor| H[Canal compatible]
    H -->|capacidad del canal| S[Sumidero]
    C -->|sin acción; coste cero| S
```

Cada cliente puede consumir un solo cupo de canal. Un paquete con dos productos sigue consumiendo una unidad de flujo. Los arcos sin acción permiten no contactar y garantizan una alternativa factible incluso con todos los cupos a cero. Se exige estado `OPTIMAL` y se reconstruye el objetivo con enteros, contrastándolo con el coste reportado por el solver.

## Qué acredita el certificado

Sea `W[i,h]` el mejor aporte entero factible del cliente `i` por el canal `h`, `C[h]` su capacidad y `x[i,h]` la decisión de asignación. Se busca maximizar:

```text
suma W[i,h] × x[i,h]

sujeto a:
  suma_h x[i,h] <= 1           para cada cliente
  suma_i x[i,h] <= C[h]        para cada canal
  x[i,h] >= 0                 solo alternativas permitidas
```

El certificado propone enteros `u[i] >= 0` y `v[h] >= 0` con:

```text
u[i] + v[h] >= W[i,h]          para toda alternativa

cota = suma_i u[i] + suma_h C[h] × v[h]
```

Por esas desigualdades, cualquier asignación factible tiene valor como máximo igual a `cota`. El verificador comprueba las desigualdades, la factibilidad de la parrilla y su valor usando aritmética entera. Si la cota y el valor coinciden, la **brecha exacta es cero** y esa asignación es óptima para el problema configurado.

La generación de precios usa holgura complementaria y restricciones de diferencias entre canales. Se reducen a un grafo de cinco nodos en el caso inicial; Bellman-Ford propone los precios. El verificador no confía en ese algoritmo: vuelve a comprobar las desigualdades completas. Un ciclo negativo o un paquete que no alcanza la cota impide emitir un certificado de optimalidad.

El certificado incluye las huellas del CSV, la configuración, la fecha y la escala. Una modificación de esos datos o de los multiplicadores se detecta. Una cota válida con brecha positiva se distingue de una prueba de optimalidad.

### Verificar de nuevo desde el CSV original

```powershell
python -m modelo.certificado --fecha 2026-11-05 --parrilla modelo/resultados/optimizador/flujo-1/parrilla.csv --certificado modelo/resultados/optimizador/flujo-1/certificado.json.gz
```

La verificación no invoca HiGHS ni OR-Tools. Reconstruye las alternativas desde el CSV y la configuración actuales, no desde el archivo intermedio del benchmark. Este es un certificado matemático verificado por **Python**, todavía sin una demostración comprobada por Lean.

## Cómo interpretar el rendimiento

Se separan preparación del modelo exacto, preparación del backend, solución, reconstrucción de parrilla y certificación. La preparación exacta común se reporta además en una estimación de tiempo completo. El RSS pico de cada trabajador se mide con `VmHWM` de Linux después de ejecutar su intérprete e incluye carga del problema, solver, parrilla y certificado. El pico del coordinador se registra por separado; no se mide memoria GPU.

El LP recibe coeficientes normalizados a unidades de valor esperado y una tolerancia dual de `1e-10`; el flujo recibe costes enteros. La matriz de beneficios canónica sigue siendo entera para ambos. La certificación posterior exige brecha exactamente cero y no acepta una aproximación por tolerancia.

La escala de los coeficientes puede cambiar el rendimiento de HiGHS aunque el problema matemático sea equivalente. Cada informe debe identificarla. No se presenta una aceleración del solver como si fuera la del proceso completo. El valor se compara como fracción exacta y cada resultado se audita también con el validador anterior.

## Alcance y límites

- Admite el objetivo `valor_esperado`, modo `ponderado`, un canal por cliente y hasta dos productos por contacto.
- `prioridad` y `jerarquia_estricta` conservan su implementación anterior; estos backends/certificados rechazan esos modos para no afirmar una equivalencia no implementada.
- Se soportan las exclusiones configuradas por atributos, ámbitos y condiciones compuestas. Nuevos presupuestos globales, cupos por producto o decisiones temporales necesitan ampliar tanto el modelo como el verificador.
- El certificado prueba optimalidad respecto de los datos y reglas formalizados. No acredita la exactitud comercial de los scores ni valida por sí solo una interpretación diferente del enunciado.
- Un resultado con distinto conjunto de clientes puede empatar exactamente en valor. Se comparan objetivo, factibilidad y el indicador de jerarquía, sin exigir IDs idénticos.

## Referencias

- [Asignación mediante flujo, OR-Tools](https://developers.google.com/optimization/flow/assignment_min_cost_flow).
- [API de min_cost_flow](https://or-tools.github.io/docs/pdoc/ortools/graph/python/min_cost_flow.html).
- [HiGHS dual simplex en SciPy](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs-ds.html).
- [Rangos numéricos y costes, código de OR-Tools](https://github.com/google/or-tools/blob/stable/ortools/graph/min_cost_flow.h).
