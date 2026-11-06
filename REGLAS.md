# Reglas del modelo NBA

Especificación de negocio basada en el [diccionario de variables y formatos](docs/reto/diccionario-datos.pdf), páginas 1-7, y el [enunciado del reto](docs/reto/enunciado.pdf), páginas 2-6. Contrastada con la configuración del repositorio el 5 de noviembre de 2026.

El objetivo es elegir productos y un canal por cliente para maximizar el valor esperado, con **cero violaciones**. Los scores de producto y canal ya están calculados. La cifra publicada a superar es **10.241,5**; no es un umbral de elegibilidad.

## 1. Entrada y significado de las variables

[`datos/clientes.csv`](datos/clientes.csv) contiene 100.000 filas, una por cliente, y 45 columnas. Los datos son sintéticos. Los dominios siguientes proceden del diccionario; no implican que el motor ya valide exhaustivamente cada dominio.

| Variable | Tipo y dominio del diccionario | Significado y uso |
| --- | --- | --- |
| `id_cliente` | Texto; CL000001 a CL100000 | Identificador único; enlaza entrada y salida. |
| `region` | Categoría: Bogotá, Antioquia, Valle, Costa Caribe, Eje Cafetero, Santanderes, Centro, Sur | Región comercial. El CSV escribe `Bogota` sin tilde; normalizar etiquetas al compararlas. |
| `estrato` | Entero, 1-6 | Perfil socioeconómico; no crea por sí solo una exclusión. |
| `edad` | Entero, 18-80 | Edad en años; el reto no fija una regla comercial adicional por edad. |
| `antiguedad_meses` | Entero, 1-240 | Meses como cliente. |
| `tipo_linea` | Postpago o Prepago | Perfil de la línea móvil. |
| `plan_datos_gb` | Entero, 2-999 | `999` significa ilimitado; no representa un consumo medido de 999 GB. |
| `consumo_datos_pct` | Decimal, 0-100 | Porcentaje consumido del plan mensual. |
| `arpu_movil` | Entero, 5.000-153.000 COP | Ingreso mensual de la línea móvil. |
| `calificacion_riesgo` | E, A, B, C, P, de mejor a peor | Elegibilidad de terminales: R02. |
| `en_mora` | Binaria, 0/1 | Saldo vencido: R01. |
| `dias_mora` | Entero: 0, 15, 30, 45, 60, 90 | Días de mora; 0 si está al día. R01 usa `en_mora`. |
| `tiene_hogar` | Binaria, 0/1 | Servicio Hogar actual: R04. |
| `arpu_hogar` | Entero, 0-231.000 COP | Ingreso mensual de Hogar; 0 si no tiene servicio. |
| `tiene_netflix` | Binaria, 0/1 | Netflix contratado con la compañía. |
| `tiene_amazon_prime` | Binaria, 0/1 | Amazon Prime contratado con la compañía. |
| `tiene_win` | Binaria, 0/1 | Win Sports contratado con la compañía. |
| `cantidad_ott` | Entero, 0-3 | Suma de las tres OTT: R05. |
| `usa_redes_sociales` | Binaria, 0/1 | Uso frecuente de redes sociales. |
| `usa_banca_digital` | Binaria, 0/1 | Uso de banca digital. |
| `compras_digitales` | Binaria, 0/1 | Compra en línea; no es una etiqueta de compra de la oferta evaluada. |
| `edad_equipo_meses` | Entero, 0-84 | Antigüedad del equipo móvil: R03. |
| `gama_equipo` | Baja, Media o Alta | Gama del equipo actual. |
| `quejas_90d` | Entero, 0-6 | Quejas de los últimos 90 días: R07. |
| `riesgo_churn` | Decimal, 0-1 | Probabilidad estimada de abandono; no es veto comercial automático. |
| `tiene_correo` | Binaria, 0/1 | Existencia de correo registrado; no equivale a autorización. |
| `autoriza_sms` | Binaria, 0/1 | Permiso de SMS: R09. |
| `autoriza_correo` | Binaria, 0/1 | Permiso de correo: R09. |
| `autoriza_whatsapp` | Binaria, 0/1 | Permiso de WhatsApp: R09. |
| `contactos_mes` | Entero, 0-8 | Contactos comerciales del mes; no fija por sí solo otro tope mensual. |
| `contactos_semana_actual` | Entero, 0-3 | Contactos de la semana antes de la corrida: R15. |
| `contactos_asesor_mes` | Entero, 0-8 | Contactos de asesor del mes: R10. |
| `contactos_sms_mes` | Entero, 0-8 | Historial mensual por SMS. |
| `contactos_correo_mes` | Entero, 0-8 | Historial mensual por correo. |
| `contactos_whatsapp_mes` | Entero, 0-8 | Historial mensual por WhatsApp. |
| `canales_contactados_mes` | Lista de asesor, sms, correo, whatsapp | Historial de canales; no prohíbe repetir un canal por sí solo. |
| `productos_ofertados_mes` | Lista de TER, VCH, OTT | Historial de productos: R06. |
| `dias_ultimo_contacto` | Entero, 0-180 | Días desde el último contacto; no hay espera mínima obligatoria definida. |
| `score_terminales` | Decimal, 0-1 | Propensión a renovar terminal. |
| `score_venta_cruzada_hogar` | Decimal, 0-1 | Propensión a contratar Hogar. |
| `score_upgrade_ott` | Decimal, 0-1 | Propensión a agregar OTT. |
| `score_canal_asesor` | Decimal, 0-1 | Probabilidad estimada de respuesta por asesor. |
| `score_canal_sms` | Decimal, 0-1 | Probabilidad estimada de respuesta por SMS. |
| `score_canal_correo` | Decimal, 0-1 | Probabilidad estimada de respuesta por correo. |
| `score_canal_whatsapp` | Decimal, 0-1 | Probabilidad estimada de respuesta por WhatsApp. |

Las listas usan `|` como separador. Una cadena vacía representa una lista vacía. La comparación de productos debe hacerse por tokens completos: `TER` no equivale a una coincidencia parcial dentro de otra palabra. El código de producto, por ejemplo `TER`, es distinto del identificador de campaña `C-TER`.

## 2. Productos y canales iniciales

| Campaña | Producto | Valor de negocio | Jerarquía inicial | Score | Canales permitidos |
| --- | --- | ---: | ---: | --- | --- |
| C-VCH | VCH: venta cruzada Hogar | 1,0 | 1 | `score_venta_cruzada_hogar` | asesor, whatsapp, correo, sms |
| C-TER | TER: renovación de terminal | 0,8 | 2 | `score_terminales` | asesor, whatsapp, correo, sms |
| C-OTT | OTT: agregar Netflix, Amazon Prime o Win | 0,4 | 3 | `score_upgrade_ott` | whatsapp, correo, sms |

| Canal | Cupo de clientes por corrida | Productos máximos por contacto | Score |
| --- | ---: | ---: | --- |
| asesor | 2.500 | 1 | `score_canal_asesor` |
| whatsapp | 15.000 | 2 | `score_canal_whatsapp` |
| correo | 30.000 | 2 | `score_canal_correo` |
| sms | 40.000 | 2 | `score_canal_sms` |

Cada campaña debe estar activa y vigente en la fecha de evaluación. El kit inicial fija vigencia del **2026-11-01 al 2026-12-31**, ambos inclusive. Estos campos, los valores y los canales se conservan en [`modelo/config/campanas.json`](modelo/config/campanas.json).

## 3. Restricciones obligatorias R01-R16

La numeración de esta sección es la del **enunciado PDF**, no la de los once registros del CSV de reglas.

| ID | Condición para permitir la acción | Alcance y efecto |
| --- | --- | --- |
| R01 | `en_mora == 0` | Si tiene mora, excluir todos los productos. |
| R02 | Para TER: `calificacion_riesgo` pertenece a `{E, A, B}` | Excluir TER a riesgos C y P; otras campañas siguen evaluándose. |
| R03 | Para TER: `edad_equipo_meses >= 18` | Con 18 meses puede competir; con 17, no. |
| R04 | Para VCH: `tiene_hogar == 0` | No ofrecer Hogar a quien ya lo tiene. |
| R05 | Para OTT: `cantidad_ott < 3` | Debe faltar al menos una de las tres OTT. |
| R06 | El código de producto no aparece en `productos_ofertados_mes` | No repetir ese producto durante el mes, aunque cambie la campaña. |
| R07 | `quejas_90d < 3` | Con 3 o más quejas, excluir todos los productos. |
| R08 | Score de producto `>= 0.35` | El umbral incluye 0,35. Se evalúa con la columna de score de cada campaña. |
| R09 | WhatsApp, correo o SMS: autorización de ese canal `== 1` | El permiso de un canal no habilita los otros. No existe una columna de autorización de asesor en este diccionario. |
| R10 | Para asesor: `contactos_asesor_mes < 2` | Con 0 o 1 llamadas previas puede competir; con 2, no. |
| R11 | Score del canal `>= 0.25` | El umbral incluye 0,25. Un score alto de producto no elimina este requisito. |
| R12 | El canal pertenece a `canales_permitidos` de la campaña | OTT no puede ir por asesor en la configuración inicial. |
| R13 | Como máximo un canal por cliente y corrida | `sin_accion` es válido; no se obliga a contactar a todo cliente. |
| R14 | Asesor: hasta 1 producto. Digital: hasta 2 productos distintos | Los dos productos de un cliente comparten el canal elegido. El máximo no obliga a llenar ambos lugares. |
| R15 | Si se contacta: `contactos_semana_actual + 1 <= 3` | Con 2 contactos previos cabe uno; con 3, no cabe otro. |
| R16 | Clientes asignados al canal `<= capacidad_por_corrida[canal]` | Un cliente con dos productos en el mismo contacto consume **un cupo**, no dos. |

Todas las restricciones aplicables se combinan con **AND**. Que un producto sea elegible no garantiza asignación: también debe existir un canal compatible y capacidad. Que un producto quede excluido no necesariamente excluye los otros.

### Ejemplos de frontera

- TER con riesgo B, equipo de 18 meses y score 0,35 supera esos tres filtros; aún necesita cumplir las demás reglas.
- Un cliente con 3 quejas queda sin ofertas aunque todos sus scores sean altos.
- Dos productos por WhatsApp cuentan como un contacto semanal y un cupo de WhatsApp en este contrato.
- Tener 3 contactos en el mes no excluye por sí solo: los topes obligatorios son el semanal total y el mensual de asesor.
- Haber usado SMS este mes no impide volver a usarlo. Haber recibido TER este mes sí impide volver a ofrecer TER.

## 4. Configuración y numeración real del kit

[`modelo/config/reglas.json`](modelo/config/reglas.json) almacena condiciones de exclusión. Una regla activa excluye cuando su condición se cumple. Por ejemplo, `edad_equipo_meses < 18` excluye TER; no describe la condición de admisión.

| Control del enunciado | Implementación/configuración actual |
| --- | --- |
| R01-R07 | Registros con los mismos IDs en `reglas.json`. |
| R08, score de producto | `parametros.priorizacion.umbral_score_producto`. |
| R09, autorizaciones | Registros R08, R09 y R10 del kit, todos con `control: "R09"`. |
| R10, llamadas de asesor | Registro R11 del kit con `control: "R10"`. |
| R11, score de canal | `parametros.canal.umbral_score_canal`. |
| R12, canales de campaña | `campanas[].canales_permitidos`. |
| R13, un canal | `parametros.politica_contacto.canales_por_cliente`. |
| R14, cantidad de productos | `parametros.politica_contacto.max_productos_por_canal`. |
| R15, tope semanal | `parametros.politica_contacto.max_contactos_semana`. |
| R16, cupos | `parametros.canal.capacidad_por_corrida`. |

Las reglas admiten alcance `global`, `campana`, `producto`, `objetivo` o `canal`; operadores `==`, `!=`, `<`, `<=`, `>`, `>=`, `en`, `no_en` y `contiene`; y el valor especial `$producto`. El motor agrega condiciones compuestas `todas`/`alguna`. La acción implementada es `excluir` y `activa` permite deshabilitar una regla.

R02 se implementa actualmente excluyendo `{C, P}`. Esto equivale a admitir `{E, A, B}` **solo dentro del dominio del diccionario**. Una categoría desconocida no debe darse por autorizada; la validación exhaustiva de dominios es una tarea distinta del filtro de elegibilidad.

## 5. Priorización y función que se maximiza

### Valor esperado oficial

Para cada producto asignado:

```text
aporte = score_producto × score_canal × valor_negocio
valor_total = suma de los aportes de todos los productos asignados
```

Si un contacto lleva dos productos, ambos aportan valor, usando el mismo score de canal, y consumen un solo cupo. Una salida con violaciones no compite en valor.

La jerarquía se reporta aparte; no se suma automáticamente al valor oficial. El enunciado pide mostrar qué tanto se respeta la preferencia de negocio y explicar su balance con el valor. El motor actual calcula su indicador entre los clientes con acción; conviene mantener explícito ese denominador al comparar implementaciones.

### Puntaje inicial de la baseline

```text
puntaje_producto = 0.6 × score_producto
                 + 0.2 × valor_negocio
                 + 0.2 × nivel_jerarquia

nivel_jerarquia: VCH = 1; TER = 0.5; OTT = 0
```

La baseline recorre clientes de mayor a menor prioridad y asigna el canal habilitado de mayor score que aún tenga cupo, cargando productos hasta su máximo. Este puntaje de selección es distinto de la métrica oficial anterior.

Los parámetros iniciales son modo `ponderado`, jerarquía `C-VCH, C-TER, C-OTT`, pesos `0.6, 0.2, 0.2` que suman 1 y desempate por score de producto y valor de negocio. El criterio alternativo de canal usa el orden `whatsapp, correo, sms, asesor`.

El motor actual usa únicamente flujo de coste mínimo con OR-Tools (`optimizacion.backend: "flujo_ortools"`) y `optimizacion.objetivo: "valor_esperado"`. Los pesos de prioridad no cambian ese objetivo. Solo se admite el modo `ponderado`; los modos `prioridad` y `jerarquia_estricta` se rechazan. La jerarquía se informa como indicador, sin imponerse al objetivo. La baseline y su preferencia de canal se describen aquí como referencia del reto; ya no se ejecutan en el motor.

## 6. Calidad de datos y coherencia

Estos controles se desprenden del diccionario y sirven para validar una entrada; no agregan restricciones comerciales nuevas:

- Una fila por ID único y todas las columnas necesarias; scores finitos entre 0 y 1; contadores enteros no negativos; binarias limitadas a 0/1 y categorías reconocidas.
- `cantidad_ott = tiene_netflix + tiene_amazon_prime + tiene_win`.
- `dias_mora == 0` si está al día; un registro contradictorio con `en_mora` requiere revisión.
- `arpu_hogar == 0` cuando no hay servicio Hogar, según la definición del diccionario.
- Tener correo y autorizar correo son señales distintas. La ausencia de dirección impide una entrega real, pero `tiene_correo` no aparece como una regla independiente entre R01-R16.
- Los campos vacíos de listas significan ausencia de elementos; los vacíos de scores, permisos o atributos requeridos no deben convertirse silenciosamente en elegibilidad.

En la revisión del CSV disponible hubo **cero inconsistencias** en la suma de OTT, en la relación mora/días y en correo autorizado sin correo registrado. El motor ya rechaza IDs duplicados, scores ausentes/no finitos y ciertos contadores inválidos; no se afirma que implemente toda la validación de dominios de las 45 variables.

El archivo no contiene horas de envío/lectura, compras observadas, costes de contacto ni mediciones de emoción. Tampoco hay una regla obligatoria de cobertura o una franja horaria concreta en estos documentos. Incorporar esas dimensiones exige nuevas variables y una política explícita.

## 7. Salida exigida

```csv
id_cliente,estado,canal,campana_1,campana_2,razon
```

- Debe existir una fila por cada cliente, incluidos los que quedan sin acción.
- `estado` es `asignado` o `sin_accion`.
- En `sin_accion`, `canal`, `campana_1` y `campana_2` quedan vacíos; `razon` explica el motivo.
- En `asignado`, hay un canal y al menos una campaña válida. `campana_2` es opcional y respeta el máximo del canal; `campana_1` corresponde a la de mayor puntaje según el criterio usado.
- `razon` debe explicar la decisión sin abrir el código: exclusiones, falta de compatibilidad, topes, cupos o elección de producto/canal.

## 8. Qué debe poder modificar negocio

Campañas, vigencias y activación; reglas sobre columnas nuevas; ámbitos de aplicación; umbrales; jerarquía y pesos; canales permitidos; capacidades; productos por contacto; topes de contacto y de llamadas. Todos los valores de negocio deben vivir en configuración.

Para comparar contra **10.241,5**, se conservan los datos, scores, valores y restricciones iniciales. Simular más cupos, otras campañas o un umbral distinto es válido como escenario de negocio, pero corresponde a otro problema de comparación.

La versión actual admite un canal y hasta dos campañas por cliente por el contrato CSV. Configurar más productos o varios canales requiere ampliar el motor y acordar un formato compatible; no basta con cambiar un número en JSON.

## Fuentes y archivos relacionados

- [Diccionario, páginas 1-4: variables; 4-7: configuración y parrilla](docs/reto/diccionario-datos.pdf).
- [Enunciado, páginas 2-4: productos, canales y R01-R16; 5-6: métrica, jerarquía y baseline](docs/reto/enunciado.pdf).
- [Configuración activa](modelo/config/), [kit original](modelo/kit_original/) y [motor y evaluación](modelo/README.md).
