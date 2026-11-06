# Motor NBA: flujo exacto y certificado

`Engine.optimize()` resuelve exclusivamente mediante **flujo de coste mínimo con OR-Tools**. La ejecución normal construye las alternativas, resuelve, verifica un certificado entero y audita las reglas antes de guardar la parrilla. Se retiraron LP, baseline, pruebas automatizadas y comparadores ejecutables.

## Ejecución normal

Desde la raíz:

```powershell
python -m modelo.ejecutar --fecha 2026-11-05
python -m modelo.exportar_evaluacion
```

La [guía de entorno](entorno.md) describe el Python WSL y la dependencia local de OR-Tools. La tarea predeterminada es `nba`. La parrilla, certificado y métricas se guardan en `modelo/resultados/nba/`; [evaluacion/nba.json](../evaluacion/nba.json) conserva el informe compacto actual.

## Construcción del problema

`optimizacion/problema.py` lee los valores decimales originales sin convertir previamente los scores a flotantes. Evalúa campañas activas y vigentes, elegibilidad, autorizaciones, reglas por ámbito, umbrales, historial y límites de contacto. Enumera todos los paquetes de uno y dos productos distintos por cliente y canal y conserva el de mayor aporte exacto.

Esta reducción es válida para el objetivo aditivo actual: no hay cupos globales por producto ni otras restricciones que acoplen el contenido de los paquetes. Los valores se convierten a enteros con una potencia de diez común; para el CSV inicial el denominador es 1.000.000.000. Se comprueban precisión y rangos int64. No se redondean scores para forzar una solución.

## Red de flujo

```mermaid
flowchart LR
    F[Fuente: N unidades] -->|capacidad 1| C[Cliente]
    C -->|capacidad 1; coste = menos valor| H[Canal compatible]
    H -->|capacidad del canal| S[Sumidero]
    C -->|sin acción; coste cero| S
```

Un cliente consume como máximo un cupo de canal. Un paquete de dos productos también consume una unidad. Los arcos sin acción permiten no contactar. El solver debe devolver `OPTIMAL`; se contrasta su coste con la reconstrucción entera de la parrilla.

## Certificado de optimalidad

Sea `W[i,h]` el mejor aporte entero factible del cliente `i` por canal `h` y `C[h]` su capacidad. El certificado propone enteros no negativos:

```text
u[i] + v[h] >= W[i,h]   para toda alternativa
cota = suma_i u[i] + suma_h C[h] × v[h]
```

Toda asignación factible tiene valor como máximo igual a esa cota. El verificador revisa las desigualdades, la factibilidad de la parrilla y su valor con aritmética entera. Solo se exporta si la cota coincide exactamente con el valor: **brecha cero**.

Los precios se generan mediante holgura complementaria y restricciones de diferencias entre canales. El verificador vuelve a comprobar las desigualdades completas. El certificado liga los datos, configuración, fecha y escala mediante sus huellas. Se rechaza si esas entradas cambian.

La auditoría independiente revisa además los controles de negocio R01–R16. Estos controles son parte de la ejecución normal del motor.

### Verificar un certificado guardado

```powershell
python -m modelo.certificado --fecha 2026-11-05 --parrilla modelo/resultados/nba/parrilla_optimo.csv --certificado modelo/resultados/nba/certificado.json.gz
```

Este comando reconstruye el problema desde el CSV original, sin invocar un solver. El certificado está comprobado por Python; no hay una demostración comprobada por Lean.

## Resultado y antecedente de selección

El motor mantiene valor exacto **10.940,0024511**, cero violaciones y brecha exacta cero para los 100.000 clientes, fecha 2026-11-05. La referencia publicada es 10.241,5; el incremento es 6,82 %.

La comparación histórica de tres repeticiones que motivó la selección está en [evaluacion/optimizador.json](../evaluacion/optimizador.json):

| Mediana histórica | LP / HiGHS | Flujo / OR-Tools |
| --- | ---: | ---: |
| Valor exacto | 10.940,0024511 | 10.940,0024511 |
| Tiempo del solver | 8,546 s | 0,164 s |
| Tiempo del backend, con preparación y parrilla | 8,694 s | 0,319 s |
| RSS pico del trabajador | 332,92 MiB | 220,73 MiB |

Los tiempos de solución excluyen la construcción común, certificación, arranque y escritura. En aquella comparación, la estimación que añadía construcción y certificación mejoró 3,75 veces. El informe conserva las huellas del código anterior, incluidos archivos retirados; es evidencia histórica, no un benchmark de la versión integrada actual. La nueva corrida registra sus propios tiempos en `evaluacion/nba.json`.

## Alcance

- Solo backend `flujo_ortools`, objetivo `valor_esperado`, modo `ponderado`, un canal y hasta dos productos distintos.
- Nuevos presupuestos globales, cupos por producto u horarios requieren ampliar el modelo y el verificador.
- La optimalidad se acredita respecto de los datos y reglas configurados; no valida comercialmente los scores ni demuestra ventas futuras.
- Puede haber parrillas distintas con exactamente el mismo valor óptimo.

## Referencias

- [Asignación por flujo, OR-Tools](https://developers.google.com/optimization/flow/assignment_min_cost_flow).
- [API de min_cost_flow](https://or-tools.github.io/docs/pdoc/ortools/graph/python/min_cost_flow.html).
- [Rangos de costes en el código de OR-Tools](https://github.com/google/or-tools/blob/stable/ortools/graph/min_cost_flow.h).
