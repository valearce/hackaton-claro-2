# Verificación matemática con Lean 4

[Lean 4](https://lean-lang.org/doc/reference/latest/) es un lenguaje de programación y un asistente de demostraciones. Permite expresar definiciones y teoremas y comprobar sus pruebas. [Mathlib](https://leanprover-community.github.io/mathlib4_docs/) aporta la biblioteca matemática de la comunidad.

Para este proyecto proponemos conservar Python/HiGHS para encontrar una asignación y utilizar Lean como verificador de un certificado. El proyecto [duality](https://github.com/madvorak/duality) y el [artículo de Dvorak y Kolmogorov](https://arxiv.org/abs/2409.08119) formalizan resultados de dualidad y alternativas de Farkas para programación lineal en Lean 4. Son una referencia para diseñar la verificación; su código no se ha incorporado a este repositorio.

## Aplicación propuesta al motor NBA

1. Definir formalmente las acciones permitidas, la elegibilidad, los cupos y el objetivo aditivo del reto.
2. Exportar desde Python la asignación y un certificado dual, ligados a las huellas de los datos y de la configuración.
3. Representar scores y valores decimales con aritmética racional exacta. Convertir números flotantes requiere comprobar todas las desigualdades; redondear el certificado no garantiza su validez.
4. Comprobar que la asignación es factible y que el certificado proporciona una cota superior para cualquier asignación factible.
5. Si el valor de la asignación coincide exactamente con la cota, concluir optimalidad para el problema formalizado. Si queda una diferencia, certificar únicamente esa diferencia.

El estado `Optimal` del solver y los controles numéricos existentes no son una demostración comprobada por Lean. Para certificar el reto completo también debe verificarse que la traducción desde las reglas de negocio y el CSV representa correctamente el problema. Una prueba sobre un modelo incorrecto no valida su interpretación del reto.

Lean reforzaría la garantía y la explicación del resultado. No aumenta por sí solo los scores, las capacidades ni la conversión comercial. La integración debe empezar por un caso pequeño verificable y medir después el coste de comprobar el conjunto completo.

## Estado

Investigación y propuesta de arquitectura, consultada el 5 de noviembre de 2026. No hay archivos `.lean`, dependencias Lean instaladas por esta tarea ni certificados formalmente comprobados en la evaluación publicada.
