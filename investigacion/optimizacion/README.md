# Modelos de optimización para el orquestador NBA

Consulta web: **5 de noviembre de 2026**. Se documentan **19 enfoques y 22 fuentes primarias**: formulaciones, estrategias de objetivos, medidas de riesgo y algoritmos. Es una selección orientada al repositorio, no una lista de toda la optimización matemática. Todos los enfoques identificados en esta revisión están incluidos.

Las descripciones técnicas remiten a documentación oficial o trabajos de sus autores. Las aplicaciones a nuestro NBA y las prioridades son **propuestas propias**, no resultados obtenidos por esas fuentes. No se instalaron ni ejecutaron nuevos optimizadores durante esta revisión.

El catálogo estructurado está en [modelos.json](modelos.json); la procedencia, alcance de lectura y enlaces están en [fuentes.json](fuentes.json). Para los artículos se revisaron fichas/resúmenes, salvo que se indique otra cosa; no se afirma revisión integral ni reproducción de sus experimentos.

Actualización posterior a la revisión: se implementaron LP, flujo de coste mínimo y certificados enteros independientes. La [guía del optimizador](../../modelo/docs/optimizador.md) describe su ejecución y los [resultados medidos](../../modelo/evaluacion/optimizador.json). La comprobación mediante Lean sigue pendiente.

## Qué problema tenemos hoy

El [motor actual](../../modelo/nba/motor.py) maximiza el valor esperado mediante flujo de coste mínimo con OR-Tools. El [reporte vigente](../../modelo/evaluacion/nba.json) registra **10.940,0024511**, cero violaciones y brecha exacta cero con certificado entero verificado por Python. La comparación LP/flujo se conserva como evidencia histórica; sus ejecutores y la suite de pruebas se retiraron. El catálogo siguiente conserva las propuestas de la revisión original.

Una formulación equivalente bien resuelta debería alcanzar el mismo máximo, dentro de la precisión definida. Otra arquitectura puede mejorar tiempo, memoria, explicaciones o validación. Agregar presupuesto, incertidumbre, horarios u otro objetivo crea una extensión que debe evaluarse aparte. No se alteran scores ni reglas para simular una mejora del benchmark.

## Lo que probaría primero

1. **Flujo de coste mínimo frente al LP.** Es la alternativa que más directamente aprovecha la estructura actual. Contrastar objetivo y auditoría y medir tiempo/memoria, sin prometer una aceleración antes de medirla. [Referencia de asignación en red](https://developers.google.com/optimization/flow/assignment_min_cost_flow).
2. **Lexicografía valor-jerarquía-fatiga.** Buscar si existen soluciones de igual valor con mejor criterio secundario. Si negocio permite perder valor, mostrar una frontera y la degradación explícita. La documentación distingue prioridades, pesos y tolerancias. [Referencia multiobjetivo](https://docs.gurobi.com/projects/optimizer/en/current/features/multiobjective.html).
3. **MILP como extensión controlada.** Probar primero equivalencia con el caso actual y después agregar un presupuesto o un cupo por producto. [Formulación MILP](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html).
4. **Bandits con presupuesto cuando haya resultados.** El artículo de conversión conecta aprendizaje y LP de asignación. Su estructura de costes no coincide necesariamente con un contacto que cuesta aunque no haya compra. [Artículo original](https://arxiv.org/abs/2206.00314).

## Mapa de enfoques

Las prioridades ordenan nuestros siguientes experimentos, no representan un ranking universal de algoritmos.

| ID | Enfoque | Tipo | Prioridad | Relación con el benchmark |
| --- | --- | --- | --- | --- |
| O01 | [Programación lineal (LP)](#o01) | modelo | P0: referencia actual | mismo problema |
| O02 | [Flujo de coste mínimo / asignación capacitada](#o02) | formulacion en red | P1: probar primero | mismo problema |
| O03 | [Programación lineal entera mixta (MILP)](#o03) | modelo | P1: extensión prioritaria | equivalente inicialmente; ampliado al agregar restricciones |
| O04 | [Programación por restricciones / CP-SAT](#o04) | paradigma y solver | P2: reglas complejas | misma formulación si solo se cambia solver; ampliado con horarios |
| O05 | [Mochila multidimensional y asignación con recursos](#o05) | familia de formulaciones | P2: presupuesto | problema ampliado |
| O06 | [Optimización multiobjetivo lexicográfica / frontera de compromiso](#o06) | estrategia de objetivos | P1: probar primero | valor principal comparable; objetivo secundario adicional |
| O07 | [Programación cuadrática (QP / MIQP)](#o07) | modelo | P3: requiere evidencia | objetivo modificado |
| O08 | [Programación cónica de segundo orden (SOCP / MISOCP)](#o08) | modelo | P3: incertidumbre estructurada | problema ampliado |
| O09 | [Optimización robusta con presupuesto de incertidumbre](#o09) | modelo de incertidumbre | P2: simulación; P3: validar | otro criterio de robustez |
| O10 | [Programación estocástica por escenarios / SAA](#o10) | modelo de incertidumbre | P3: requiere escenarios | problema ampliado |
| O11 | [Optimización distribucionalmente robusta (DRO Wasserstein)](#o11) | modelo de incertidumbre | P3: requiere datos | objetivo y supuestos nuevos |
| O12 | [CVaR: optimización de pérdidas en la cola](#o12) | medida de riesgo incorporable al objetivo | P3: requiere escenarios | criterio de riesgo adicional |
| O13 | [Restricciones probabilísticas (chance constraints)](#o13) | restriccion de incertidumbre | P3: solo con distribución validada | extensión operativa; reglas obligatorias siguen siendo duras |
| O14 | [Planificación multiperiodo y horizonte rodante](#o14) | modelo temporal y politica de reoptimizacion | P2: siguiente extensión temporal | problema temporal ampliado |
| O15 | [Optimización submodular de presupuesto/cobertura](#o15) | familia de objetivos combinatorios | P3: solo si se valida la estructura | objetivo nuevo |
| O16 | [Bandits contextuales con presupuesto (CBwK)](#o16) | aprendizaje y decision secuencial | P3: prometedor con feedback | aprende un objetivo comercial nuevo; no reemplaza los scores oficiales en la comparación fija |
| O17 | [MDP restringido / aprendizaje por refuerzo](#o17) | modelo de decision secuencial | P4: posterior a bandits | problema secuencial distinto |
| O18 | [Optimización bayesiana](#o18) | metodo de busqueda de parametros | P4: capa auxiliar | capa de ajuste, no motor de asignación |
| O19 | [Metaheurística evolutiva multiobjetivo (NSGA-II)](#o19) | algoritmo heuristico | P4: casos sin formulación manejable | solo comparable si objetivos y restricciones coinciden |

## Fichas de todos los enfoques

<a id="o01"></a>
### O01. Programación lineal (LP)

**Idea:** Optimiza una función lineal con restricciones lineales.

**Aplicación propuesta:** Conservar el problema cliente-canal con el mejor paquete factible y capacidades compartidas.

**Datos o decisiones adicionales:** No exige nuevas variables para contrastarlo con el caso actual.

**Límite:** La integralidad de nuestro caso depende de su estructura de asignación; restricciones adicionales pueden perderla.

**Experimento:** Usar el valor, la factibilidad y la cota dual como referencia para cada alternativa.

**Fuentes:** [S01: SciPy: linprog / HiGHS dual simplex](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs-ds.html).

<a id="o02"></a>
### O02. Flujo de coste mínimo / asignación capacitada

**Idea:** Representa decisiones como flujo por arcos con costes y capacidades.

**Aplicación propuesta:** Arcos fuente-cliente-canal-sumidero y una opción sin acción; coste igual al negativo del valor.

**Datos o decisiones adicionales:** No exige nuevas variables para contrastarlo con el caso actual.

**Límite:** Solo equivale al LP mientras la decisión por cliente/canal pueda condensarse en un paquete sin acoplamientos adicionales.

**Experimento:** Comparar objetivo, cero violaciones, memoria y tiempo con HiGHS; escalar decimales exactamente y comprobar desbordamientos.

**Fuentes:** [S02: OR-Tools: Assignment as a Minimum Cost Flow Problem](https://developers.google.com/optimization/flow/assignment_min_cost_flow).

<a id="o03"></a>
### O03. Programación lineal entera mixta (MILP)

**Idea:** Añade decisiones enteras o binarias a restricciones y objetivos lineales.

**Aplicación propuesta:** Representar presupuestos, cupos por producto y combinaciones incompatibles entre ofertas.

**Datos o decisiones adicionales:** costes y límites nuevos, si se añaden

**Límite:** No se debe relajar a LP y redondear sin comprobar factibilidad; hay que reportar incumbente, cota y brecha.

**Experimento:** Reproducir el caso original y después agregar una única restricción de negocio por escenario.

**Fuentes:** [S03: SciPy: milp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html).

<a id="o04"></a>
### O04. Programación por restricciones / CP-SAT

**Idea:** Busca soluciones discretas sujetas a restricciones; CP-SAT exige formulación entera de las restricciones.

**Aplicación propuesta:** Agregar implicaciones, incompatibilidades, ventanas de contacto y recursos temporales.

**Datos o decisiones adicionales:** ventanas y duración de contactos para planificación temporal

**Límite:** FEASIBLE no equivale a OPTIMAL. El escalado decimal y los límites numéricos requieren revisión.

**Experimento:** Comparar con MILP usando exactamente las mismas reglas, límite temporal y precisión del objetivo.

**Fuentes:** [S04: OR-Tools: CP-SAT Solver](https://developers.google.com/optimization/cp/cp_solver); [S22: OR-Tools: The Job Shop Problem](https://developers.google.com/optimization/scheduling/job_shop).

<a id="o05"></a>
### O05. Mochila multidimensional y asignación con recursos

**Idea:** Selecciona elementos con valor y consumo de uno o varios recursos limitados.

**Aplicación propuesta:** Elegir contactos bajo dinero, minutos de asesor y capacidad de canal, conservando exclusividad por cliente.

**Datos o decisiones adicionales:** coste de contacto, duración o consumo de recursos

**Límite:** Resolver una mochila por canal separadamente puede asignar al mismo cliente varias veces o desperdiciar alternativas.

**Experimento:** Construir una formulación conjunta y medir valor neto y utilización del presupuesto.

**Fuentes:** [S05: OR-Tools: The Knapsack Problem](https://developers.google.com/optimization/pack/knapsack); [S03: SciPy: milp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html).

<a id="o06"></a>
### O06. Optimización multiobjetivo lexicográfica / frontera de compromiso

**Idea:** Combina objetivos por pesos o prioridades; una prioridad superior se protege mediante restricciones y tolerancias explícitas.

**Aplicación propuesta:** Primero maximizar valor; después mejorar jerarquía o reducir fatiga conservando ese valor dentro de una tolerancia acordada.

**Datos o decisiones adicionales:** definición del objetivo secundario, tolerancia de degradación

**Límite:** Fijar el óptimo exacto conserva una cara óptima integral del caso actual; una tolerancia positiva o nuevas restricciones pueden perder esa garantía. Definir si jerarquía significa un conteo o un porcentaje.

**Experimento:** Construir una frontera valor-jerarquía, mostrar sacrificios y verificar integralidad en cada etapa.

**Fuentes:** [S06: Gurobi: Multiple Objectives](https://docs.gurobi.com/projects/optimizer/en/current/features/multiobjective.html); [S03: SciPy: milp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html).

<a id="o07"></a>
### O07. Programación cuadrática (QP / MIQP)

**Idea:** Incluye un término cuadrático; la estructura de la matriz determina convexidad.

**Aplicación propuesta:** Penalizar concentración o modelar interacciones entre decisiones cuando haya una justificación medible.

**Datos o decisiones adicionales:** matriz de interacciones o penalización validada

**Límite:** Un QP continuo puede dar contactos fraccionarios; contactos discretos requieren una formulación entera adecuada.

**Experimento:** Comparar un objetivo ampliado con y sin penalización y auditar la pérdida del valor oficial.

**Fuentes:** [S07: CVXPY: Quadratic program](https://www.cvxpy.org/examples/basic/quadratic_program.html).

<a id="o08"></a>
### O08. Programación cónica de segundo orden (SOCP / MISOCP)

**Idea:** Permite restricciones convexas de norma y ciertas formulaciones de riesgo.

**Aplicación propuesta:** Representar límites de exposición a incertidumbre cuando un modelo estadístico justifique esa geometría.

**Datos o decisiones adicionales:** estructura de incertidumbre y estimaciones fiables

**Límite:** La versión continua no produce necesariamente decisiones discretas; no toda restricción probabilística es cónica.

**Experimento:** Justificar la aproximación de riesgo y comparar soluciones enteras y cobertura fuera de muestra.

**Fuentes:** [S08: CVXPY: Second-order cone program](https://www.cvxpy.org/examples/basic/socp.html).

<a id="o09"></a>
### O09. Optimización robusta con presupuesto de incertidumbre

**Idea:** Busca decisiones resistentes a variaciones admitidas de los coeficientes, aceptando un compromiso con el valor nominal.

**Aplicación propuesta:** Investigar sensibilidad a errores de scores o capacidad; proponer un presupuesto de incertidumbre ajustable.

**Datos o decisiones adicionales:** rangos o errores de estimación de scores/capacidades

**Límite:** Perturbaciones inventadas solo justifican una simulación; el valor nominal puede bajar al protegerse.

**Experimento:** Evaluar curvas de protección frente a valor nominal en escenarios separados del benchmark fijo.

**Fuentes:** [S09: The Price of Robustness](https://pubsonline.informs.org/doi/abs/10.1287/opre.1030.0065).

<a id="o10"></a>
### O10. Programación estocástica por escenarios / SAA

**Idea:** Optimiza decisiones ante escenarios de parámetros inciertos, con posibles etapas de adaptación.

**Aplicación propuesta:** Planear capacidad y asignación considerando entregas, disponibilidad o respuestas futuras.

**Datos o decisiones adicionales:** escenarios representativos, probabilidades o muestras históricas, momento en que se observa la incertidumbre

**Límite:** Decisiones previas no pueden depender de información futura: imponer no anticipatividad.

**Experimento:** Reservar escenarios de evaluación y contrastar la política con una solución determinista bajo el mismo seguimiento.

**Fuentes:** [S10: mpi-sppy: stochastic programming](https://mpi-sppy.readthedocs.io/en/stable/).

<a id="o11"></a>
### O11. Optimización distribucionalmente robusta (DRO Wasserstein)

**Idea:** Optimiza frente a distribuciones adversas dentro de una vecindad de una distribución empírica.

**Aplicación propuesta:** Investigar decisiones menos sensibles a que la distribución de respuesta cambie respecto del historial.

**Datos o decisiones adicionales:** muestras de resultados, distancia y radio de ambigüedad calibrados

**Límite:** Las reformulaciones y garantías dependen de supuestos; no se transfieren automáticamente a nuestro problema discreto.

**Experimento:** Separación temporal y evaluación bajo cambios de distribución, mostrando sensibilidad al radio.

**Fuentes:** [S11: Data-driven Distributionally Robust Optimization Using the Wasserstein Metric](https://arxiv.org/abs/1505.05116).

<a id="o12"></a>
### O12. CVaR: optimización de pérdidas en la cola

**Idea:** Mide pérdidas medias en una fracción de resultados desfavorables; debe definirse sobre pérdidas con la orientación correcta.

**Aplicación propuesta:** Limitar malos resultados de una cartera de contactos y compararlos con su valor medio.

**Datos o decisiones adicionales:** pérdidas por escenario, nivel de confianza, peso de aversión al riesgo

**Límite:** CVaR no es un solver; las restricciones discretas siguen necesitando un modelo adecuado.

**Experimento:** Reportar promedio, cola de pérdidas y estabilidad fuera de muestra para varios niveles de aversión.

**Fuentes:** [S12: CVXPY: cvar implementation and definition](https://www.cvxpy.org/_modules/cvxpy/atoms/cvar.html); [S10: mpi-sppy: stochastic programming](https://mpi-sppy.readthedocs.io/en/stable/).

<a id="o13"></a>
### O13. Restricciones probabilísticas (chance constraints)

**Idea:** Exige que una condición incierta se cumpla con una probabilidad mínima bajo el modelo de escenarios.

**Aplicación propuesta:** Estudiar capacidad operativa incierta o niveles de entrega en una extensión del sistema.

**Datos o decisiones adicionales:** distribución o escenarios, probabilidad admisible de fallo operativo

**Límite:** No convertir permisos, elegibilidad ni topes obligatorios del reto en restricciones que puedan violarse probabilísticamente.

**Experimento:** Medir la frecuencia de cumplimiento en escenarios reservados y contrastar sus intervalos de incertidumbre.

**Fuentes:** [S13: mpi-sppy: Chance Constraints](https://mpi-sppy.readthedocs.io/en/stable/chance_constraints.html).

<a id="o14"></a>
### O14. Planificación multiperiodo y horizonte rodante

**Idea:** Planifica sobre un horizonte finito y recalcula al avanzar y observar el estado.

**Aplicación propuesta:** Coordinar contactos de varios días, preservar cupos futuros y actualizar historial después de cada ejecución.

**Datos o decisiones adicionales:** calendario, estado persistente de contactos, disponibilidad futura y expiraciones

**Límite:** La referencia MPC proviene de control; su adaptación a campañas es nuestra propuesta, no un resultado demostrado para NBA.

**Experimento:** Simulación de varios días con llegadas idénticas, sin reutilizar cupos ya consumidos ni anticipar respuestas.

**Fuentes:** [S14: do-mpc: Basics of model predictive control](https://www.do-mpc.com/en/latest/theory_mpc.html); [S22: OR-Tools: The Job Shop Problem](https://developers.google.com/optimization/scheduling/job_shop).

<a id="o15"></a>
### O15. Optimización submodular de presupuesto/cobertura

**Idea:** Aprovecha rendimientos marginales decrecientes en determinados modelos de cobertura o influencia.

**Aplicación propuesta:** Investigar diversidad de audiencia y redundancia entre contactos cuando exista evidencia de saturación.

**Datos o decisiones adicionales:** función de cobertura o influencia, evidencia de rendimientos decrecientes

**Límite:** Las garantías dependen de submodularidad y de las restricciones; no vale trasladar un factor de aproximación sin comprobar supuestos.

**Experimento:** Validar la función y comparar con un óptimo pequeño antes de escalar.

**Fuentes:** [S15: Optimal Budget Allocation: Theoretical Guarantee and Efficient Algorithm](https://proceedings.mlr.press/v32/soma14.html).

<a id="o16"></a>
### O16. Bandits contextuales con presupuesto (CBwK)

**Idea:** Aprende recompensas de las acciones elegidas mientras consume recursos; el trabajo revisado combina estimaciones de conversión con LP.

**Aplicación propuesta:** Aprender qué oferta/canal funciona y asignar exploración con presupuesto, respetando elegibilidad externa.

**Datos o decisiones adicionales:** exposiciones y conversiones, probabilidad de la acción registrada, costes y recursos, soporte entre políticas

**Límite:** El CSV no contiene ese feedback. En el artículo los costes ocurren con la conversión; nuestros contactos pueden costar aun sin compra.

**Experimento:** Evaluación temporal IPS/DR cuando sea identificable, análisis de varianza y un experimento posterior por cliente.

**Fuentes:** [S16: Contextual Bandits with Knapsacks for a Conversion Model](https://arxiv.org/abs/2206.00314); [S17: Vowpal Wabbit: Offline Policy Evaluation](https://vowpalwabbit.org/docs/vowpal_wabbit/python/latest/tutorials/off_policy_evaluation.html).

<a id="o17"></a>
### O17. MDP restringido / aprendizaje por refuerzo

**Idea:** Modela acciones que afectan estados y recompensas futuras, con límites de recursos.

**Aplicación propuesta:** Investigar secuencias de incentivos, retención y efectos futuros de la presión comercial.

**Datos o decisiones adicionales:** trayectorias de acciones y resultados, estados y transiciones, recompensa y horizonte definidos

**Límite:** El problema contrafactual y la evaluación de políticas requieren evidencia; un CSV estático no basta.

**Experimento:** Construir primero un entorno validado y comparar con una política sencilla y bandits bajo el mismo presupuesto.

**Fuentes:** [S18: Model-based Constrained MDP for Budget Allocation in Sequential Incentive Marketing](https://arxiv.org/abs/2303.01049).

<a id="o18"></a>
### O18. Optimización bayesiana

**Idea:** Selecciona evaluaciones de una función costosa usando un modelo sustituto y un criterio de adquisición.

**Aplicación propuesta:** Ajustar hiperparámetros del perfil o políticas simuladas cuando la evaluación sea costosa.

**Datos o decisiones adicionales:** objetivo de validación fiable, presupuesto de evaluaciones, espacio de búsqueda

**Límite:** No sustituye la asignación exacta ni justifica cambiar scores del benchmark; conservar un test sin usar para ajuste.

**Experimento:** Comparar con búsqueda aleatoria usando igual presupuesto y particiones fijas.

**Fuentes:** [S19: A Tutorial on Bayesian Optimization](https://arxiv.org/abs/1807.02811).

<a id="o19"></a>
### O19. Metaheurística evolutiva multiobjetivo (NSGA-II)

**Idea:** Mantiene una población de candidatos para explorar compromisos entre varios objetivos.

**Aplicación propuesta:** Explorar una frontera cuando objetivos complejos se evalúan mediante una simulación.

**Datos o decisiones adicionales:** evaluador de objetivos, codificación y reparación de restricciones, varias semillas y presupuesto de búsqueda

**Límite:** No usar una buena solución encontrada como certificado del óptimo; comparar con una cota o caso exacto.

**Experimento:** Medir factibilidad, estabilidad por semilla y calidad de la frontera frente a un método exacto pequeño.

**Fuentes:** [S20: pymoo: NSGA-II](https://pymoo.org/algorithms/moo/nsga2.html).

## Detalles de formulación que importan en nuestro caso

### La red debe permitir no contactar

Para un cliente `i` y canal `h`, definir `V[i,h]` como el mejor valor de un paquete elegible, incluyendo sus restricciones de productos. Usar arcos fuente-cliente de capacidad 1, cliente-canal de capacidad 1 y coste `-V[i,h]`, y canal-sumidero con su cupo. Para poder enviar un flujo de un elemento por cliente sin forzar contactos, agregar cliente-sumidero con coste cero como opción `sin_accion`. Los canales incompatibles no tienen arco. Esta es nuestra adaptación al NBA de la formulación de asignación en red, no código ya implementado.

Escalar los costes decimales a enteros con una precisión definida y comprobar límites numéricos. No redondear scores arbitrariamente: podría cambiar empates o el óptimo. Comparar por valor y factibilidad; diferentes parrillas pueden empatar en valor.

### La segunda etapa lexicográfica necesita una definición precisa

Primero resolver `V* = max valor(x)`. Después optimizar un criterio secundario sobre soluciones con `valor(x) = V*`, o con `valor(x) >= V* - epsilon` si negocio permite degradación. Son alternativas distintas. El uso de Gurobi en la fuente ilustra el concepto; no obliga a introducir ese solver.

Análisis propio: con el óptimo exacto del politopo integral de asignación, la igualdad define una cara óptima integral. Con `epsilon > 0`, errores numéricos o nuevas restricciones, esa garantía puede perderse y hay que comprobar integralidad o usar MILP. Si al precomputar paquetes existen empates de valor, conservar o desempatar también por el objetivo secundario para no eliminar alternativas útiles.

El indicador de jerarquía del repo es un porcentaje sobre clientes asignados. Mejorar solo el número de aciertos puede cambiar también su denominador: no afirmar mejora del porcentaje sin recalcular ambos. Fatiga también necesita una definición explícita, por ejemplo un coste basado en el historial disponible; no equivale a una emoción inferida.

### Presupuesto, incertidumbre y tiempo deben tener su propio escenario

Los costes monetarios por contacto, las distribuciones de error de los scores y las trayectorias de respuesta no están en el CSV. Se pueden crear escenarios sintéticos identificados como tales, pero no presentarlos como comportamiento observado. Las restricciones obligatorias y los permisos siguen siendo duros incluso si se usa riesgo o probabilidad para otras variables operativas.

Para planear varios días, actualizar contactos, productos ya ofertados, vigencia y capacidad tras cada decisión. Repetir la optimización estática sin actualizar estado no es una política multiperiodo correcta. Una solución que conoce respuestas futuras en la simulación tiene ventaja indebida.

## Métodos complementarios y su función

| Herramienta | Función y límite |
| --- | --- |
| [Marginales del LP](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs-ds.html) | Explicar el valor local de capacidad adicional. Los precios duales son locales y deben contrastarse reoptimizando cambios grandes. |
| [Benders en Pyomo](https://pyomo.readthedocs.io/en/stable/_modules/pyomo/contrib/benders/benders_cuts.html) | Método de descomposición para modelos con estructura adecuada; no una familia predictiva ni una mejora automática. |
| [Lean 4](../verificacion-lean.md) | Propuesta para verificar formalmente certificados y restricciones; no busca por sí solo una asignación mejor. |
| [Autoencoder/PCA/GMM/Isomap](../../modelo/README.md#validación-de-autoencoder-gaussianos-e-isomap) | Representaciones y perfiles; menor reconstrucción no acredita mayor conversión ni mayor valor oficial. |
| [HNSW](../../modelo/README.md#hnsw) | Búsqueda aproximada de vecinos. Recortar candidatos de asignación sin una cota puede eliminar el óptimo global. |

## Protocolo para comparar sin engañarnos

1. Congelar CSV, configuración, fecha y precisión del objetivo mediante huellas. Usar el [entorno de pruebas](../../modelo/docs/entorno.md) y registrar qué parte usa CPU o GPU.
2. Separar pruebas del mismo problema de escenarios con restricciones u objetivos nuevos. Para una formulación equivalente, contrastar el máximo y la auditoría, no exigir IDs idénticos cuando existan empates.
3. Guardar factibilidad, objetivo calculado independientemente, cota, brecha, estado del solver, tiempo y memoria. Una solución factible por límite de tiempo no es un óptimo acreditado.
4. En métodos con incertidumbre, reservar escenarios fuera del ajuste; medir promedio, cola, estabilidad y violaciones operativas, conservando las reglas obligatorias.
5. Para políticas aprendidas, disponer de logs de exposición, acción, probabilidad de elección y resultado. Comprobar soporte y supuestos antes de usar IPS/DR; no tratar una estimación contrafactual como garantía de despliegue. [Evaluación de políticas](https://vowpalwabbit.org/docs/vowpal_wabbit/python/latest/tutorials/off_policy_evaluation.html).
6. Para hiperparámetros y heurísticas, fijar presupuesto de búsqueda, varias semillas y un conjunto final sin usar para selección. Toda ganancia se atribuye a la métrica efectivamente evaluada.

## Fuentes primarias consultadas

El alcance de lectura de cada fuente está detallado en [fuentes.json](fuentes.json). Los enlaces son referencias; no se copiaron artículos completos ni sus experimentos.

- **S01**: [SciPy: linprog / HiGHS dual simplex](https://docs.scipy.org/doc/scipy/reference/optimize.linprog-highs-ds.html). Formulación LP, estados, tolerancias y marginales.
- **S02**: [OR-Tools: Assignment as a Minimum Cost Flow Problem](https://developers.google.com/optimization/flow/assignment_min_cost_flow). Asignación mediante redes y límites de aplicabilidad.
- **S03**: [SciPy: milp](https://docs.scipy.org/doc/scipy/reference/generated/scipy.optimize.milp.html). Variables enteras, restricciones y cotas.
- **S04**: [OR-Tools: CP-SAT Solver](https://developers.google.com/optimization/cp/cp_solver). Aritmética entera y diferencia entre FEASIBLE y OPTIMAL.
- **S05**: [OR-Tools: The Knapsack Problem](https://developers.google.com/optimization/pack/knapsack). Selección de elementos con valor y consumo de capacidad.
- **S06**: [Gurobi: Multiple Objectives](https://docs.gurobi.com/projects/optimizer/en/current/features/multiobjective.html). Objetivos ponderados, jerárquicos y tolerancias de degradación; referencia conceptual, no dependencia propuesta obligatoria.
- **S07**: [CVXPY: Quadratic program](https://www.cvxpy.org/examples/basic/quadratic_program.html). Formulación cuadrática convexa y ejemplo media-varianza.
- **S08**: [CVXPY: Second-order cone program](https://www.cvxpy.org/examples/basic/socp.html). Restricciones de norma y formulación cónica.
- **S09**: [The Price of Robustness](https://pubsonline.informs.org/doi/abs/10.1287/opre.1030.0065). Resumen editorial y referencia original; no revisión integral de la demostración.
- **S10**: [mpi-sppy: stochastic programming](https://mpi-sppy.readthedocs.io/en/stable/). Escenarios y problemas multietapa; índice de métodos y ejemplos.
- **S11**: [Data-driven Distributionally Robust Optimization Using the Wasserstein Metric](https://arxiv.org/abs/1505.05116). Resumen de la versión revisada en 2017; no reproducción de experimentos ni revisión completa de pruebas.
- **S12**: [CVXPY: cvar implementation and definition](https://www.cvxpy.org/_modules/cvxpy/atoms/cvar.html). Definición sobre muestras, parámetro beta e implementación.
- **S13**: [mpi-sppy: Chance Constraints](https://mpi-sppy.readthedocs.io/en/stable/chance_constraints.html). Restricción probabilística sobre escenarios e indicadores binarios.
- **S14**: [do-mpc: Basics of model predictive control](https://www.do-mpc.com/en/latest/theory_mpc.html). Horizonte finito y reoptimización con horizonte desplazado; adaptación a campañas propuesta por nosotros.
- **S15**: [Optimal Budget Allocation: Theoretical Guarantee and Efficient Algorithm](https://proceedings.mlr.press/v32/soma14.html). Ficha y resumen de ICML; garantías sujetas a la estructura del modelo, no transferidas al NBA.
- **S16**: [Contextual Bandits with Knapsacks for a Conversion Model](https://arxiv.org/abs/2206.00314). Resumen: conversión, presupuesto y políticas que resuelven un LP; no reproducción del estudio.
- **S17**: [Vowpal Wabbit: Offline Policy Evaluation](https://vowpalwabbit.org/docs/vowpal_wabbit/python/latest/tutorials/off_policy_evaluation.html). Evaluación contrafactual con logs y estimadores IPS/DR; requisitos de identificación deben comprobarse.
- **S18**: [Model-based Constrained MDP for Budget Allocation in Sequential Incentive Marketing](https://arxiv.org/abs/2303.01049). Resumen del modelo secuencial de incentivos; no reproducción de resultados.
- **S19**: [A Tutorial on Bayesian Optimization](https://arxiv.org/abs/1807.02811). Resumen: optimización de evaluaciones costosas con modelos sustitutos.
- **S20**: [pymoo: NSGA-II](https://pymoo.org/algorithms/moo/nsga2.html). Algoritmo evolutivo multiobjetivo e implementación.
- **S21**: [Pyomo: Benders cut generator](https://pyomo.readthedocs.io/en/stable/_modules/pyomo/contrib/benders/benders_cuts.html). Generación de cortes y requisitos del componente; no benchmark de rendimiento.
- **S22**: [OR-Tools: The Job Shop Problem](https://developers.google.com/optimization/scheduling/job_shop). Precedencias y recursos temporales; no es directamente un modelo de campañas.
