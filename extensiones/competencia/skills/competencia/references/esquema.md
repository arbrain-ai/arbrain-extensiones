# Esquema · `embudos.json` (`competidores-embudos/v1`)

Una ficha por canal con su embudo a grandes rasgos (a dónde manda el video, regalo, oferta pagada, promesa, vehículo y
mecanismo). Cada dato lleva **fuente, fecha y nivel de evidencia**. Vive en `.claude/memory/extensiones/competencia/
embudos.json`, lo arma `competencia.py construir` desde las fichas curadas y lo valida `scripts/validar.py` (si el
validador y este documento no coinciden, manda el validador y este documento se corrige). Es el mismo esquema que usa
el autor de la extensión con su propio nicho: un archivo suyo pasa este validador tal cual.

## Raíz

| Campo | Tipo | Qué es |
|---|---|---|
| `esquema` | `"competidores-embudos/v1"` | Nombre y versión. Si cambia la forma, sube a v2. |
| `version` | int | 1 |
| `generado` | ISO 8601 con zona | Cuándo se armó el archivo. |
| `corte` | `AAAA-MM-DD` | Día al que se refiere la evidencia. |
| `que_es`, `documentado_en` | str | Descripción en una línea y puntero a este archivo. |
| `reglas` | str[] | Reglas de captura (solo páginas públicas, nada sin fuente…). |
| `fuentes_base` | objeto | Rutas citables del censo (`$DATOS/censos/…`), las páginas abiertas, el universo y las fichas curadas. |
| `cobertura` | `{fichas, completas, parciales, faltantes:{slug: [campo…]}}` | Debe cuadrar con las fichas. |
| `lo_que_se_repite` | `Patron[]` (0 a 8) | Lo que se repite y lo que nadie hace (`patrones.json`; vacío mientras hay pocas fichas). |
| `fichas` | `Ficha[]` | Una por canal. |

`Patron` = `{texto, respaldo: [slug…], lectura_de_levy: bool}`. Cada slug de `respaldo` debe existir en `fichas`. `lectura_de_levy: true` = interpretación, no observación.

## Ficha

| Campo | Tipo | Qué es |
|---|---|---|
| `slug`, `nombre`, `channel_id`, `handle`, `idioma`, `capas` | | Identidad del canal: los mismos que `universo.json` (ids verificados por la API). |
| `motivo` | str | Por qué entró (lo nombró el dueño, o salió de la búsqueda y él lo marcó). |
| `muestra` | `{videos, desde, hasta, con_transcript, descripciones_de[], censo}` | Qué se leyó: los últimos N videos largos, sus fechas, cuántos tienen texto hablado y de dónde vino la descripción (`youtube-data-api`). |
| `destinos_video` | `Destino[]` | A dónde mandan las descripciones. |
| `cta_hablado` | `Cta[]` | Lo que pide de viva voz, con minuto. |
| `regalo_entrada` | `Regalo[]` | La puerta gratis (o de pago bajo, si así entra). |
| `oferta_pagada` | `Oferta[]` | Lo que cobra, con precio si se vio. |
| `promesa` | `Promesa[]` | La promesa **en sus palabras** (cita textual). |
| `vehiculo` | str[] | Forma de entrega. Valores usados: `comunidad_gratis`, `comunidad_pago`, `lead_magnet_correo`, `recurso_sin_registro`, `curso_gratis_youtube`, `curso_pago_unico`, `plataforma_de_cursos`, `academia_suscripcion`, `suscripcion`, `formacion_en_vivo`, `formacion_de_socio`, `programa_por_aplicacion`, `producto_bajo_precio`, `agencia`, `newsletter`, `libro`, `sesiones_en_vivo`, `mentorias_grupales`, `servicio_conferencias`, `canal_whatsapp`, `eventos`, `patrocinio_afiliado`, `software`. Se puede añadir un valor nuevo; el validador solo exige que la lista no esté vacía. |
| `mecanismo` | `{texto, en_sus_palabras: bool, lectura_de_levy?: bool, dato}` | El «cómo» que presenta. Si `en_sus_palabras` es `false`, `lectura_de_levy` debe ser `true`. |
| `<campo>_estado` | str | **Obligatorio cuando una lista va vacía**: dice por qué (`no_visto: …`). Vacío no es cero. |
| `no_visto` | str[] | Lo que no se pudo ver o comprobar. |
| `cobertura` | `{estado: completa\|parcial, faltan: [campo…]}` | Calculada (ver abajo). |

### Piezas

- **Destino** `{rol, nombre, url, etiqueta, en_videos, de_videos, posicion_mediana, destino_final, http, dato}`. `rol`: `comunidad_gratis`, `comunidad_pago`, `lead_magnet_correo`, `recurso_sin_registro`, `curso_gratis_youtube`, `cobro_directo`, `academia_suscripcion`, `masterclass_socio`, `agencia`, `newsletter`, `web_propia`, `producto_propio`, `portafolio`, `canal_whatsapp`, `servicio_conferencias`, `afiliado_o_patrocinio`, `otro_video`, `mixto_bitly`, `comunidad`, `externo` (herramienta o fuente citada). `etiqueta` es el texto de la línea donde aparece el enlace. `en_videos/de_videos` = en cuántos de los N videos del censo está. `posicion_mediana` = lugar del enlace dentro de la descripción (1 = el primero). `destino_final`/`http` = a dónde llegó al seguir redirecciones.
- **Cta** `{video_id, titulo, publicado, minuto "M:SS", lugar: apertura|durante|cierre, pide, cita, dato}`. `cita` es **literal** de los subtítulos públicos; el constructor la copia del tramo pedido y falla si no hay texto. `pide` es el resumen (lo único no literal).
- **Regalo** `{nombre, que_da, requiere, url, dato}`. `requiere`: `nada`, `correo (no se envió)`, `cuenta de Skool (no se creó)`, `registro (no se hizo)`…
- **Oferta** `{nombre, precio: Precio|null, url, dato}`. `Precio` = `{monto: número, moneda, recurrencia: mensual|trimestral|anual|pago_unico|null, texto}`; `texto` copia lo que dice la página (descuentos, alzas anunciadas). `precio: null` = no se vio; la razón va en `dato.nota`. Si hay precio, el `dato` debe ser `precio_visto` o `archivo_wayback`. Un alza anunciada no sustituye al precio actual.
- **Promesa** `{cita, donde, dato}`.

### Dato (evidencia de cada afirmación)

`{fuente, fecha: AAAA-MM-DD, nivel, nota?, respaldo?}`. `fuente` = URL o archivo; `respaldo` = copia del texto visible en `.claude/memory/extensiones/competencia/evidencia/<slug>__<clave>.txt` (el HTML crudo queda en `$DATOS/paginas/`).

| `nivel` | Significa |
|---|---|
| `enlace_visible` | El enlace está en la descripción; su destino no se abrió (o no respondió). |
| `pagina_abierta` | La página pública se abrió hoy (GET sin sesión) y se leyó. |
| `precio_visto` | La página abierta muestra el precio. |
| `dicho_en_video` | Está en el transcript o subtítulos, con minuto. |
| `archivo_wayback` | Visto en una captura de Wayback Machine con su fecha (la página actual ya no lo muestra). |
| `heredado` | Viene de una investigación anterior del dueño con su fecha original; no se reabrió hoy. |

## Completa o parcial

Una ficha es **completa** si `destinos_video`, `cta_hablado`, `regalo_entrada`, `oferta_pagada`, `promesa`, `vehiculo` y `mecanismo` tienen al menos un dato, y alguna oferta tiene precio visto. Si no, es **parcial** y `cobertura.faltan` dice qué falta (`precio_de_la_oferta` cuando hay oferta pero sin precio). Si un canal no tiene regalo o no tiene oferta, la ficha queda parcial con su `_estado`: el archivo no distingue «no existe» de «no lo vi».

## Lo que el script pone solo (no lo escribas en la ficha curada)

Identidad (del universo), `muestra` y `destinos_video` (del censo), `cobertura` (calculada), la `cita` de cada
`cta_hablado` (del tramo de subtítulos que pidas) y la fuente, fecha y respaldo de un dato `{"pagina": "<clave>"}`.
Formato de la ficha curada: `curar-fichas.md`.
