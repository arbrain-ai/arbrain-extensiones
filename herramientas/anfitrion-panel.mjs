#!/usr/bin/env node
/**
 * Anfitrión de prueba para el panel de una extensión, sin la app (20 nov 2026). Hace lo que hará Arbrain (SPEC §2):
 * pinta `panel.entrada` en un iframe `sandbox="allow-scripts"` (origen opaco, CSP sin red), contesta sus `pedir` con
 * la fuente `ext:` (solo lo declarado; lo demás `negado`), le manda el tema, re-lee los archivos cada 3 s y, cuando el
 * panel toca un botón, muestra arriba el texto que Levy recibiría (o la URL que abriría). No ejecuta ninguna acción.
 *
 *   node herramientas/anfitrion-panel.mjs --ext extensiones/competencia --cerebro <carpeta del cerebro> \
 *        [--datos <CLAUDE_PLUGIN_DATA>] [--puerto 4791]
 *   abrir http://127.0.0.1:4791/?modo=oscuro            (#canal=<slug> abre una ficha; #clic=<accion> toca un botón)
 */
import { createServer } from 'node:http'
import { existsSync, readFileSync } from 'node:fs'
import { extname, join, normalize, resolve } from 'node:path'
import { resolverFuente, textoDeAccion } from './fuente-ext.mjs'

const arg = (k, d) => { const i = process.argv.indexOf(`--${k}`); return i > 0 ? process.argv[i + 1] : d }
const EXT = resolve(arg('ext', '.'))
const CEREBRO = resolve(arg('cerebro', process.cwd()))
const DATOS = arg('datos') ? resolve(arg('datos')) : null
const PUERTO = Number(arg('puerto', 4791))
const manifiesto = () => JSON.parse(readFileSync(join(EXT, 'arbrain.json'), 'utf8'))
const CSP = "sandbox allow-scripts; default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:; font-src data:; connect-src 'none'; frame-src 'none'; form-action 'none'; base-uri 'none'"
const TIPOS = { '.html': 'text/html; charset=utf-8', '.svg': 'image/svg+xml', '.css': 'text/css', '.js': 'text/javascript', '.png': 'image/png' }

const host = m => `<!doctype html><html lang="es"><head><meta charset="utf-8"><title>Anfitrión · ${m.nombre}</title>
<style>html,body{margin:0;height:100%;background:#08090c;font:13px -apple-system,system-ui,sans-serif;color:#c9ccd3}
#barra{display:flex;gap:14px;align-items:center;height:38px;padding:0 14px;border-bottom:1px solid #1d2028;background:#0c0e12}
#barra b{color:#fff}#levy{margin-left:auto;color:#f2c66d;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:70%}
iframe{display:block;width:100%;height:calc(100% - 39px);border:0}</style></head><body>
<div id="barra"><b>Arbrain</b><span>Extensiones › ${m.nombre}</span><span id="levy" data-prueba="accion"></span></div>
<iframe id="panel" sandbox="allow-scripts" src="/panel/${m.panel.entrada.replace(/^panel\//, '')}${'${HASH}'}"></iframe>
<script>
const modo = new URLSearchParams(location.search).get('modo') || 'oscuro'
const f = document.getElementById('panel'), levy = document.getElementById('levy'), fechas = {}
const mandar = m => f.contentWindow.postMessage(m, '*')
async function datos(fuente) {
  const r = await fetch('/fuente?f=' + encodeURIComponent(fuente)).then(r => r.json())
  if (fechas[fuente] !== undefined && fechas[fuente] === r.fecha) return
  fechas[fuente] = r.fecha
  mandar({ tipo: 'datos', fuente, valor: r.valor, fecha: r.fecha, estado: r.estado })
}
addEventListener('message', async ev => {
  if (ev.source !== f.contentWindow) return
  const m = ev.data || {}
  if (m.tipo === 'hola') mandar({ tipo: 'tema', modo })
  if (m.tipo === 'pedir') datos(m.fuente)
  if (m.tipo === 'listo') document.body.dataset.listo = '1'
  if (m.tipo === 'accion') {
    const r = await fetch('/accion?d=' + encodeURIComponent(m.destino)).then(r => r.json())
    levy.textContent = r.texto ? 'Levy recibiría: «' + r.texto + '»' : r.url ? 'Abriría en tu navegador: ' + r.url : 'Acción no declarada: ' + m.destino
    document.body.dataset.accion = m.destino
  }
})
setInterval(() => Object.keys(fechas).forEach(datos), 3000)
</script></body></html>`

createServer((req, res) => {
  const u = new URL(req.url, 'http://x')
  const json = o => { res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' }); res.end(JSON.stringify(o)) }
  try {
    if (u.pathname === '/') {
      const hash = u.searchParams.get('hash') ? '#' + u.searchParams.get('hash') : ''
      res.writeHead(200, { 'content-type': 'text/html; charset=utf-8' })
      return res.end(host(manifiesto()).replace('${HASH}', hash.replace(/[^#a-z0-9=&-]/gi, '')))
    }
    if (u.pathname === '/fuente') return json(resolverFuente(u.searchParams.get('f'), manifiesto(), { cerebro: CEREBRO, datos: DATOS }))
    if (u.pathname === '/accion') {
      const d = u.searchParams.get('d') || ''
      const url = /^url:(https?:\/\/.+)$/.exec(d)?.[1] || null
      return json({ texto: textoDeAccion(d, manifiesto()), url })
    }
    if (u.pathname.startsWith('/panel/')) {
      const base = join(EXT, 'panel')
      const p = normalize(join(base, decodeURIComponent(u.pathname.slice('/panel/'.length))))
      if (!p.startsWith(base + '/') || !existsSync(p)) { res.writeHead(404); return res.end() }
      const h = { 'content-type': TIPOS[extname(p)] || 'application/octet-stream' }
      if (extname(p) === '.html' || extname(p) === '.svg') h['content-security-policy'] = CSP
      res.writeHead(200, h)
      return res.end(readFileSync(p))
    }
    res.writeHead(404); res.end()
  } catch (e) { res.writeHead(500); res.end(String(e)) }
}).listen(PUERTO, '127.0.0.1', () => console.log(`anfitrión en http://127.0.0.1:${PUERTO}/ · panel de ${EXT}`))
