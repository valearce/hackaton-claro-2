# Orquestador NBA configurable — prototipo v3

Motor Next Best Action para el reto de la hackatón. Todo número o regla vive en `config/`.

## Correr

```bash
pip install pandas numpy scipy streamlit anthropic
streamlit run app.py                        # consola: borrador vs publicada, copiloto (ANTHROPIC_API_KEY), versiones
python3 motor/generar_datos.py              # 100.000 clientes sintéticos -> datos/clientes.csv (solo si no hay base real)
python3 motor/test_casos.py                 # compara la línea base con los 5 casos de ejemplo
python3 motor/correr.py [ruta/clientes.csv] # línea base y óptimo + validador -> salidas/
python3 motor/escenarios.py                 # cambios de negocio resueltos solo con configuración
python3 motor/prueba_robustez.py 30         # 30 configuraciones al azar: 0 violaciones y mismo valor que el LP exacto
python3 motor/costo_reglas.py               # radar: cuánto valor cuesta cada regla, umbral y cupo
```

## Piezas

- `motor/nba.py`: elegibilidad con reglas como datos, opciones canal × combo, asignación (`codicioso` = línea base del reto, `optimo` = programación lineal con precios sombra), explicación y métricas.
- Solver (`optimizacion.solver`): `dual` (por defecto; precios sombra + LP pequeño para empates, con certificado de optimalidad) o `lp` (HiGHS completo).
- Reglas compuestas: varias filas con el mismo `id` se combinan con Y. Reglas de canal aceptan alcance `global`.
- `motor/validar_generico.py`: validador independiente para cualquier configuración.
- `motor/frases.py`: frase en español para el asesor o el equipo de campañas, varias plantillas por caso.
- `app.py`: consola Streamlit; el copiloto usa el modelo de `NBA_MODELO` (por defecto claude-sonnet-5-5) y valida cada propuesta antes de aplicarla.
- `motor/validar.py`: validador independiente de R01–R16 (no reutiliza la lógica del motor).
- `config/`: archivos del kit. Parámetros nuevos opcionales: `optimizacion.algoritmo` (codicioso|optimo), `optimizacion.bono_jerarquia` (0 = máximo valor).
- Reglas: operadores `== != < <= > >= en no_en contiene no_contiene entre`; alcance `global | campana | grupo | canal`; acción `excluir | exigir`.

## Nota

`test_casos.py` muestra 1 diferencia esperada (CL000741: WhatsApp en vez de SMS): la parrilla de ejemplo viene de la corrida completa de 100.000, donde el cupo de WhatsApp ya estaba agotado cuando la línea base llegó a ese cliente.
