/**
 * La fuente `ext:` del contrato de paneles (SPEC §2), como referencia para la app y para probar paneles sin ella
 * (20 nov 2026). Puro salvo la lectura del archivo.
 *
 *   resolverFuente('ext:$CEREBRO/.claude/memory/extensiones/competencia/embudos.json', manifiesto, { cerebro, datos })
 *     → { estado: 'ok' | 'vacio' | 'negado', valor, fecha, error? }
 *
 * Reglas (las mismas que tendrá `fuentes.ts`):
 *   1. Solo lo que el `arbrain.json` instalado declara en `panel.datos`, letra por letra. Lo demás: `negado`.
 *   2. `$CEREBRO/…` además tiene que caer dentro de `permisos.lee`; `$DATOS/…` es `${CLAUDE_PLUGIN_DATA}`.
 *   3. La ruta resuelta, ya sin enlaces, no puede salir de la carpeta que abre su permiso (nada de `..` ni enlaces que
 *      escapen); solo archivos `.json`.
 *   4. No existe todavía = `vacio` (el panel dice «sin dato»); JSON roto = `vacio` con `error`. Nunca un cero inventado.
 */
import { readFileSync, realpathSync, statSync } from 'node:fs'
import { isAbsolute, relative, resolve, sep } from 'node:path'

const LIMITE = 8 * 1024 * 1024

export function declarada(fuente, manifiesto) {
  if (typeof fuente !== 'string' || !fuente.startsWith('ext:')) return null
  const ruta = fuente.slice(4)
  const panel = manifiesto?.panel
  if (!panel || !Array.isArray(panel.datos) || !panel.datos.includes(ruta)) return null
  if (!/\.json$/.test(ruta) || ruta.includes('..') || ruta.includes('\\')) return null
  const m = /^\$(CEREBRO|DATOS)\/(.+)$/.exec(ruta)
  if (!m) return null
  if (m[1] === 'DATOS') return { raiz: 'datos', rel: m[2], permiso: '' }
  const permiso = (manifiesto.permisos?.lee || []).find(l => m[2].startsWith(l))
  return permiso ? { raiz: 'cerebro', rel: m[2], permiso } : null
}

const dentro = (base, p) => { const r = relative(base, p); return r && !r.startsWith('..') && !isAbsolute(r) && !r.split(sep).includes('..') }

export function resolverFuente(fuente, manifiesto, raices) {
  const d = declarada(fuente, manifiesto)
  if (!d) return { estado: 'negado', valor: null, fecha: null }
  const base = raices[d.raiz]
  if (!base) return { estado: 'negado', valor: null, fecha: null, error: `sin raíz ${d.raiz}` }
  const p = resolve(base, d.rel)
  if (!dentro(resolve(base), p)) return { estado: 'negado', valor: null, fecha: null }
  let real, techo
  try { real = realpathSync(p) } catch { return { estado: 'vacio', valor: null, fecha: null } }
  try { techo = realpathSync(resolve(base, d.permiso || '.')) } catch { return { estado: 'negado', valor: null, fecha: null } }
  // Lo leído, ya sin enlaces, tiene que seguir dentro de la carpeta que el permiso abre (no solo dentro del cerebro).
  if (!dentro(techo, real)) return { estado: 'negado', valor: null, fecha: null }
  const st = statSync(real)
  if (!st.isFile() || st.size > LIMITE) return { estado: 'vacio', valor: null, fecha: null, error: 'no es un archivo o es muy grande' }
  try {
    return { estado: 'ok', valor: JSON.parse(readFileSync(real, 'utf8')), fecha: st.mtime.toISOString() }
  } catch (e) {
    return { estado: 'vacio', valor: null, fecha: st.mtime.toISOString(), error: 'JSON roto' }
  }
}

/** El texto que Levy recibe por una acción `chat:<id>` (o null si la extensión no la declara). */
export function textoDeAccion(destino, manifiesto) {
  const m = /^chat:([a-z0-9-]+)$/.exec(destino || '')
  if (!m) return null
  return (manifiesto?.panel?.acciones || []).find(a => a.id === m[1])?.pide ?? null
}
