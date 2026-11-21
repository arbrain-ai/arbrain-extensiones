# Curar fichas: de lo que se vio a una ficha que pasa el validador

Una ficha dice **qué hace** un canal para convertir a quien lo ve en cliente, con la evidencia de cada afirmación.
No dice si le funciona: un enlace no dice cuántos hicieron clic y un precio publicado no dice cuántos pagan.

## El orden (por lotes de 3 a 5 canales)

1. `competencia.py ver <slug>`: qué dominios repite en sus descripciones, en cuántos videos y cómo cierra.
2. `competencia.py paginas --sugeridas --canales <slug>`: abre sus destinos propios (comunidad, curso, agenda, web).
   Lee el texto en `evidencia/<slug>__<clave>.txt` antes de escribir nada.
3. Escribe `fichas/<slug>.json` (formato abajo; ejemplo inventado en `ficha-ejemplo.json`).
4. `competencia.py construir --seco`: si algo no tiene respaldo, el error dice qué y dónde. Corrige y repite.
5. `competencia.py construir`: escribe `embudos.json` y el panel lo pinta.

## El formato de la ficha curada

| Campo | Qué pones | Lo que hace el script |
|---|---|---|
| `slug` | El del universo | Trae nombre, id, handle, idioma y capas |
| `roles` | `{"<dominio o prefijo de URL>": ["<rol>", "<nombre que ve el dueño>"]}`. `["ignorar"]` lo saca | Arma `destinos_video` desde el censo: lo que tiene rol entra; sin rol, lo que se repite en `minimo_repeticion` videos (2) |
| `cta_hablado` | `{video_id, desde, hasta, lugar, pide}`. `pide` es tu resumen | Copia la `cita` LITERAL de ese tramo de subtítulos; falla si no hay texto |
| `regalo_entrada` | `{nombre, que_da, requiere, url, dato}` | Completa el `dato` |
| `oferta_pagada` | `{nombre, url, precio, dato}`. `precio` = `{monto, moneda, recurrencia, texto}` o `null` | Exige `nivel: precio_visto` si hay precio |
| `promesa` | `{cita, donde, dato}` con la frase tal cual | Comprueba que la frase está literal en la página o en los subtítulos |
| `vehiculo` | Lista de vehículos (`esquema.md`; puedes agregar uno nuevo) | El panel los traduce con `taxonomia.json` |
| `mecanismo` | `{texto, en_sus_palabras, lectura_de_levy?, dato}` | — |
| `<campo>_estado` | Por qué un campo va vacío: `no_visto: sin página de precios pública` | Sin esto, un campo vacío no pasa |
| `no_visto` | Lo que no pudiste comprobar | — |

**El `dato`, en corto:** `{"pagina": "<clave>"}` para una página que abriste (pon `"nivel": "precio_visto"` si
muestra el precio), `{"video": "<id>", "minuto": "M:SS"}` para algo dicho en un video, o el dato completo
`{fuente, fecha, nivel, nota?}` si viene de otra fuente (`nivel: heredado` si no lo reabriste hoy).

## Qué rol tiene cada enlace

`comunidad_gratis`, `comunidad_pago`, `lead_magnet_correo` (regalo a cambio del correo), `recurso_sin_registro`,
`curso_gratis_youtube`, `cobro_directo`, `curso_pago_unico`, `academia_suscripcion`, `programa_por_aplicacion`,
`masterclass_socio`, `agencia` (también consulta o servicio), `newsletter`, `web_propia`, `producto_propio`,
`canal_whatsapp`, `servicio_conferencias`, `afiliado_o_patrocinio`, `otro_video`, `externo` (herramienta o fuente
citada). Los tres últimos no son su embudo: el panel no los muestra en «sus videos mandan a».

## Lo que no se hace

- No registrarse, no dejar el correo, no agendar, no comprar, no mandar formularios: solo lo público.
- No completar por analogía («los demás cobran 50, este también»). Si no se vio, `null` y la nota de por qué.
- No mezclar observación con lectura: lo tuyo va en `lectura_de_levy: true`.
- No pegar datos personales de terceros (correos, teléfonos): el texto de evidencia ya los tapa.
