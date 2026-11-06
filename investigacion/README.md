# Investigación y alternativas

| Tema | Material y aplicación |
| --- | --- |
| [Modelos de optimización para NBA](optimizacion/README.md) | Catálogo de 19 enfoques, 22 fuentes primarias, aplicación propuesta y experimentos prioritarios |
| [Receptividad y horarios](receptividad-horarios.md) | Revisión de seis estudios, límites de la evidencia y diseño de un experimento de contacto |
| [Catálogo de fuentes](fuentes.json) | Referencias, DOI, enlaces públicos y procedencia de las copias locales de lectura |
| [Verificación matemática con Lean](verificacion-lean.md) | Propuesta para comprobar restricciones y certificados de optimalidad |
| [Autoencoder, PCA, gaussianos e Isomap](../modelo/README.md#validación-de-autoencoder-gaussianos-e-isomap) | Protocolo, resultados sobre clientes reservados y límites de interpretación |
| [HNSW](../modelo/README.md#hnsw) | Búsqueda aproximada de perfiles similares y protocolo de evaluación propuesto |

Los experimentos ejecutados y sus métricas están en [`../modelo/evaluacion/`](../modelo/evaluacion/). Lean y HNSW se han investigado como extensiones; todavía no están incorporados a la ejecución del motor.

`estudios/` conserva las copias locales de lectura y está excluido de Git. Los enlaces públicos y su procedencia permanecen en `fuentes.json`. La transcripción del reto está en [`../docs/reto/transcripcion.md`](../docs/reto/transcripcion.md).
