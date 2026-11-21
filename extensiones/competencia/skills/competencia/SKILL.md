---
name: competencia
description: "Tu censo propio de los canales de YouTube de tu nicho: Levy da de alta tu nicho, busca candidatos con tu llave de YouTube, tú marcas quién es competencia o referente, y él censa sus últimos videos (a dónde mandan, qué piden en voz alta), abre sus páginas de oferta públicas y cura una ficha por canal con evidencia fechada (qué venden y a qué precio, su regalo, su promesa, su vehículo). El panel Competencia dice qué modelo de negocio predomina y quién vende qué. Cada domingo re-censa y dice qué cambió. Usar ante «mis competidores», «quién vende qué en mi nicho», «qué modelo predomina», «agrega este canal a mi competencia», «busca competidores de mi nicho», «corre el censo», «cura las fichas», «qué cambió en mis competidores», «a cuánto vende X», «qué regala X», «a dónde manda X sus videos» o «da de alta mi nicho»."
metadata:
  resumen: "Mira a tus competidores de YouTube con evidencia: qué venden, a qué precio y qué modelo predomina en tu nicho."
---

# Competencia: tu nicho, tu censo, tus fichas

La investigación es del dueño, no de la extensión: su universo, su censo y sus fichas viven en **su** cerebro y se
hacen con **su** llave de YouTube. Lo que trae la extensión es el método: cómo se elige a quién mirar, cómo se censa,
qué cuenta como evidencia y cómo se cura una ficha sin inventar nada.

## La pluma

```bash
C="${CLAUDE_PLUGIN_ROOT}/skills/competencia/scripts/competencia.py"   # viene en la extensión «Competencia»; corre desde tu carpeta de Arbrain
export CLAUDE_PLUGIN_DATA="${CLAUDE_PLUGIN_DATA}"                     # la caché regenerable (censos crudos, HTML, subtítulos)
python3 "$C" estado          # SIEMPRE primero: qué hay, qué falta, si hay llave y cuánta cuota queda hoy
```

En Windows usa `python` si `python3` no existe. Todos los comandos, con sus banderas, en el encabezado del script
(`python3 "$C" --help`). Códigos: **2** falta algo o la evidencia no respalda una ficha (la línea dice qué) · **4**
falta la llave · **5** se llegó al tope de cuota del día (dilo y sigue mañana; nunca subas el tope sin su sí).

## Dónde vive

`.claude/memory/extensiones/competencia/` (lo lee el panel; versionado en su rama):

| Archivo | Qué es | Quién lo escribe |
|---|---|---|
| `universo.json` | Su nicho, sus palabras, su canal y los canales que marcó (esquema `arbrain.universo-youtube/v1`) | `alta`, `marcar`, `censo` (suscriptores) |
| `candidatos.json` | Lo que propuso la búsqueda, sin marcar | `buscar` |
| `taxonomia.json` | Sus modelos de negocio (por defecto, los 7 de `references/taxonomia-por-defecto.json`) | `alta` la copia; el dueño la edita |
| `fichas/<slug>.json` | Lo que Levy curó de cada canal, con evidencia | Levy, con `references/curar-fichas.md` |
| `embudos.json` | Lo que pinta el panel (esquema `competidores-embudos/v1`) | `construir` (solo si pasa el validador) |
| `paginas-abiertas.json`, `evidencia/` | Páginas públicas abiertas y su texto visible | `paginas` |
| `estado-semanal.json`, `cambios/` | Qué cambió cada semana | `estudio` (la tarea del domingo) |

Lo regenerable (censos crudos, HTML, subtítulos, huellas, contador de cuota) va en `${CLAUDE_PLUGIN_DATA}`: se pierde
al quitar la extensión y no pasa nada. Nunca escribas en la carpeta de la extensión.

## La llave

Es la del dueño (cuota gratuita de 10,000 unidades al día; la extensión se frena en 2,000). Si `estado` dice
`llave_youtube: false`: la tienda de Arbrain la pide al instalar. Si aún no la tiene, explícale en una línea cómo
sacarla (`como_conseguirla` de `arbrain.json`) y que la pegue en la tienda, **no en el chat**. Si ya la pegó en el
chat, guárdala con `printf '%s' '<llave>' | python3 "$C" llave` (queda en `~/.config/arbrain/extensiones/llaves.env`,
0600, fuera del cerebro) y no la repitas nunca en una respuesta. Costos: `buscar` 100 unidades por palabra; un censo,
unas 2 o 3 por canal.

## 1. Alta (una vez, de una pregunta a la vez)

1. Su nicho en **sus** palabras («nutriólogas que atienden en línea en México»), no en las tuyas.
2. Cómo lo buscaría su cliente: 2 a 4 palabras (cada una cuesta 100 unidades al buscar).
3. Su canal, si tiene (`--canal @handle`). Idioma y país si no es español de México.
4. Los 3 a 10 competidores que ya conoce: cada uno con `marcar <@handle o URL> --capa competencia`.

```bash
python3 "$C" alta --nicho "<su nicho>" --palabras "<palabra 1>, <palabra 2>" --idiomas es --pais MX [--canal @suyo]
python3 "$C" buscar --por-consulta 25      # propone; no marca a nadie
python3 "$C" candidatos
```

Enséñale los candidatos en una tabla corta (nombre, suscriptores, un video de ejemplo) y que él marque cada uno:
`competencia` (le habla a su misma gente con una oferta parecida), `referente` (no compite, pero conviene estudiarlo)
o `ninguno`. **Nada entra al universo sin su marca**; si dice «todos», confirma la lista una vez.

## 2. Censo

```bash
python3 "$C" censo --n 5 --subs 2          # últimos 5 largos por canal; subtítulos de los 2 más nuevos (con yt-dlp)
python3 "$C" pendientes                    # qué falta censar o curar
python3 "$C" ver <slug>                    # lo que dejó el censo de un canal: dominios, cierre y menciones con minuto
```

Sin `yt-dlp` el censo corre igual pero no lee lo que piden en voz alta (`cta_hablado` queda con su `_estado`).

## 3. Páginas y fichas

```bash
python3 "$C" paginas --sugeridas           # sus destinos propios más repetidos; revisa la lista antes de abrir
python3 "$C" paginas --abrir-sugeridas     # o una por una: --slug <s> --clave <k> --url <https://…>
python3 "$C" cita <video_id> --desde 9:30 --hasta 10:40   # texto con minuto para elegir el tramo de una cita
python3 "$C" construir                     # fichas + censo → embudos.json; si no pasa el validador, no escribe
```

Cura por lotes de 3 a 5 canales con `references/curar-fichas.md` (formato y ejemplo en `references/ficha-ejemplo.json`).
Reglas que no se negocian: solo páginas públicas (no te registres, no compres, no envíes formularios); un dato sin
fuente no entra (va a `<campo>_estado` o `no_visto`); el precio solo con la página abierta que lo muestra; la promesa
y lo que piden en voz alta, **literales**; tu interpretación se marca `lectura_de_levy: true`. Vacío no es cero.

## 4. Lo que le dices al dueño

Con `embudos.json` construido, el panel **Competencia** (sección Contenido) ya lo pinta. En el chat, corto: cuántos
canales, qué modelo predomina (`estado` › `modelos`) y **una** cosa que se repite o que nadie hace, con quién la
respalda. Si se repite algo en varias fichas, puedes escribir `patrones.json` (hasta 8 líneas `{texto, respaldo:
[slugs], lectura_de_levy}`) y volver a `construir`. Nunca compares sus números con cifras de un tercero que no viste.

## 5. Cada semana

La tarea `estudio-semanal` (domingo 20:00) corre `competencia.py estudio`: re-censa, compara la huella de cada canal
contra la semana anterior y re-abre solo las páginas de quien cambió; deja `cambios/cambios-<fecha>.md`. Cuando el
dueño pregunte «¿qué cambió?», lee ese archivo y dile qué ficha conviene reabrir (no la reescribas sin evidencia nueva).

## La taxonomía es suya

`taxonomia.json` decide qué modelos ve el panel. Si su industria tiene otro (consulta individual, franquicia, venta
de producto físico), agrégalo con `id`, `nombre` y qué `vehiculos` o `roles` lo delatan; el panel y `estado` lo leen
en la siguiente lectura. No borres un modelo que ya usan sus fichas sin decírselo. Al actualizarse la extensión, su
taxonomía no se pisa: si `estado` trae `taxonomia_por_completar`, corre `taxonomia --completar` (solo agrega las
llaves nuevas, como los umbrales de alto ticket por moneda; lo suyo se queda igual) y díselo en una línea.
