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

## Mercadeo por cercanía para Claro

La propuesta conecta una valla de campaña con una oportunidad de contacto: proximidad → permiso y frecuencia → campaña y canal elegibles → oferta → medición. La pestaña Cercanía utiliza un recorrido simulado, antenas y vallas con radios configurables y un cliente de prueba. Las posiciones son ficticias y las distancias se calculan geométricamente. Una oportunidad de contacto no demuestra que alguien haya visto el anuncio ni que haya comprado.

| Etapa | Aplicación propuesta a Claro | Evidencia que se necesita |
| --- | --- | --- |
| Valla y campaña | Asociar cada pieza a Hogar, renovación de terminal u OTT; definir vigencia y canal | Inventario de ubicaciones, identificador de pieza y campaña vigente |
| Cercanía | Simular un recorrido por las zonas de antenas y vallas; conectar ubicación del operador en una integración futura | Posición simulada, radio, disponibilidad de la zona y hora del escenario |
| Perfilamiento | Aplicar elegibilidad del NBA: producto, mora, quejas, autorizaciones y saturación | Perfil autorizado y reglas oficiales |
| Activación | Preparar la siguiente mejor oferta por un canal permitido y con límites de contacto | Consentimiento verificable, disponibilidad del canal, cupos y registro de contactos |
| Experimentación | Comparar valla sola, contacto digital solo, combinación y control | Asignación aleatoria por cliente o zona, tamaño de muestra, visitas/conversiones observadas e intervalos de incertidumbre |

En la prueba local solo se cuentan evaluaciones, oportunidades y bloqueos. Para hablar de ventas incrementales hacen falta resultados observados y un grupo de comparación; los scores del NBA son valores esperados.

La integración futura de una red de operador puede apoyarse en la [especificación CAMARA Location Verification](https://github.com/camaraproject/DeviceLocation/blob/main/code/API_definitions/location-verification.yaml), que contempla verificación de áreas y respuestas parciales. El prototipo actual utiliza exclusivamente la simulación de antenas y vallas.
