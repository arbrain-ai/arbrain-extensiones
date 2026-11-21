# Extensiones de Arbrain

El catálogo curado de extensiones para tu cerebro de Arbrain. Cada extensión agrega skills (y, si trae, un panel y
tareas que corren solas) sin esperar una versión nueva de Arbrain. Se instalan como plugins de Claude Code.

## Instalar

Desde Arbrain: sección **Extensiones**, o dile a Levy «instálame el mapa de negocio».

A mano, desde tu carpeta de Arbrain:

```bash
claude plugin marketplace add arbrain-ai/arbrain-extensiones --scope local
claude plugin install mapa-de-negocio@arbrain --scope local
```

Actualizar: `claude plugin marketplace update arbrain && claude plugin update mapa-de-negocio@arbrain --scope local`.
Quitar: `claude plugin uninstall mapa-de-negocio@arbrain --scope local` (lo que hiciste con ella se queda en tu cerebro).

## Extensiones

| Extensión | Qué hace |
|---|---|
| `mapa-de-negocio` | La Radiografía del negocio de tu cliente y su mapa vivo en el Lienzo |
| `competencia` | Tu censo de los canales de YouTube de tu nicho: qué venden, a qué precio y qué modelo predomina (trae panel) |

## Para quien publica

- Cada extensión: `extensiones/<nombre>/` con `.claude-plugin/plugin.json` (formato de Claude Code) y `arbrain.json`
  (requisitos, permisos, panel, tareas; esquema en `esquemas/arbrain-extension.schema.json`).
- La versión vive solo en `plugin.json` y se sube en cada publicación.
- Antes de publicar: `node herramientas/validar.mjs` (corre también `claude plugin validate`).
- Un panel se prueba sin la app con `node herramientas/anfitrion-panel.mjs --ext extensiones/<nombre> --cerebro <carpeta>`:
  lo pinta aislado como Arbrain, le da solo las fuentes `ext:` declaradas y muestra el texto que Levy recibiría por cada
  botón. `herramientas/fuente-ext.mjs` es la regla de la fuente `ext:` (con sus pruebas en `fuente-ext.test.mjs`).

Licencia: Apache-2.0.
