#!/usr/bin/env node
/**
 * Valida el catálogo de extensiones de Arbrain antes de publicarlo (20 nov 2026).
 *
 *   node herramientas/validar.mjs            # desde la raíz del catálogo
 *
 * 1. `claude plugin validate` sobre el catálogo y cada extensión (formato de Claude Code; la fuente de verdad es él).
 * 2. `arbrain.json` de cada extensión contra `esquemas/arbrain-extension.schema.json` (lo que Arbrain lee y Claude
 *    Code no): requisitos, permisos, panel y licencia. Sin dependencias: chequeo a mano de las reglas del esquema.
 * 3. Reglas de la casa: el nombre del catálogo y el de plugin.json coinciden; un panel declarado existe; ninguna
 *    extensión trae CLAUDE.md (Claude Code no lo carga) ni rutas absolutas a la máquina del autor.
 * Código 0 = limpio; 1 = hay errores (se listan).
 */
import { execFileSync } from 'node:child_process'
import { existsSync, readdirSync, readFileSync, statSync } from 'node:fs'
import { join, resolve } from 'node:path'

const RAIZ = resolve(process.argv[2] || '.')
const errores = []
const mal = (donde, que) => errores.push(`${donde}: ${que}`)
const leer = p => JSON.parse(readFileSync(p, 'utf8'))

function claudeValidate(ruta) {
  try {
    execFileSync('claude', ['plugin', 'validate', ruta], { stdio: 'pipe' })
  } catch (e) {
    mal(ruta, 'claude plugin validate falló\n' + String(e.stdout || e.message))
  }
}

const SEMVER = /^(>=|\^|~)?\d+\.\d+\.\d+$/
const SLUG = /^[a-z0-9-]+$/
function validarArbrain(dir, a) {
  const d = `${dir}/arbrain.json`
  const permitidas = ['$schema', 'esquema', 'nombre', 'resumen', 'frases', 'requiere', 'permisos', 'panel', 'tareas', 'licencia']
  for (const k of Object.keys(a)) if (!permitidas.includes(k)) mal(d, `campo desconocido «${k}»`)
  if (a.esquema !== 'arbrain.extension/v1') mal(d, 'esquema debe ser arbrain.extension/v1')
  if (typeof a.nombre !== 'string' || a.nombre.length < 2 || a.nombre.length > 40) mal(d, 'nombre de 2 a 40 letras')
  if (typeof a.resumen !== 'string' || a.resumen.length < 10 || a.resumen.length > 140) mal(d, 'resumen de 10 a 140 letras')
  const r = a.requiere || {}
  if (!SEMVER.test(r.arbrain || '')) mal(d, 'requiere.arbrain como >=X.Y.Z')
  if (!Array.isArray(r.skills_base) || r.skills_base.some(s => !SLUG.test(s))) mal(d, 'requiere.skills_base: lista de nombres')
  for (const l of r.llaves || []) if (!/^[a-z0-9_]+$/.test(l.clave || '') || !l.para) mal(d, `llave mal declarada: ${JSON.stringify(l)}`)
  const p = a.permisos || {}
  for (const k of ['lee', 'escribe', 'red']) if (!Array.isArray(p[k])) mal(d, `permisos.${k} debe ser lista`)
  for (const k of ['lienzo', 'programa']) if (typeof p[k] !== 'boolean') mal(d, `permisos.${k} debe ser true/false`)
  for (const ruta of [...(p.lee || []), ...(p.escribe || [])]) {
    if (ruta.startsWith('/') || ruta.includes('..')) mal(d, `permiso fuera del cerebro: ${ruta}`)
    if (/^\.claude\/skills\//.test(ruta)) mal(d, `una extensión no escribe en las skills de la base: ${ruta}`)
  }
  if (a.panel !== null) {
    const pn = a.panel || {}
    if (!/^panel\/[A-Za-z0-9_./-]+\.html$/.test(pn.entrada || '')) mal(d, 'panel.entrada debe ser panel/<archivo>.html')
    else if (!existsSync(join(dir, pn.entrada))) mal(d, `panel.entrada no existe: ${pn.entrada}`)
    if (!Array.isArray(pn.datos) || !pn.datos.length || pn.datos.some(x => !/^(\$DATOS|\$CEREBRO)\/[A-Za-z0-9_./-]+$/.test(x)))
      mal(d, 'panel.datos: lista de $DATOS/... o $CEREBRO/...')
    for (const x of (pn.datos || []).filter(x => x.startsWith('$CEREBRO/'))) {
      const rel = x.slice('$CEREBRO/'.length)
      if (!(p.lee || []).some(l => rel.startsWith(l))) mal(d, `el panel lee ${rel} pero permisos.lee no lo declara`)
    }
  }
  for (const t of a.tareas || []) {
    if (!SLUG.test(t.id || '') || !/^\S+( \S+){4}$/.test(t.cada || '') || !/^\.\/[A-Za-z0-9_./-]+$/.test(t.corre || ''))
      mal(d, `tarea mal declarada: ${JSON.stringify(t)}`)
    else if (!existsSync(join(dir, t.corre))) mal(d, `la tarea ${t.id} corre algo que no existe: ${t.corre}`)
    for (const k of t.necesita || []) if (!(r.llaves || []).some(l => l.clave === k)) mal(d, `la tarea ${t.id} necesita «${k}» y requiere.llaves no la declara`)
  }
  if ((a.tareas || []).length && p.programa !== true) mal(d, 'trae tareas: permisos.programa debe ser true')
  if (!['gratis', 'membresia'].includes(a.licencia?.nivel)) mal(d, 'licencia.nivel: gratis o membresia')
}

function sinFugas(dir) {
  const pila = [dir]
  while (pila.length) {
    const x = pila.pop()
    for (const n of readdirSync(x)) {
      const f = join(x, n)
      if (statSync(f).isDirectory()) { if (n !== '__pycache__') pila.push(f); continue }
      if (n === 'CLAUDE.md') mal(f, 'Claude Code no carga CLAUDE.md de un plugin: ponlo en una skill')
      if (/\.(md|py|mjs|js|json|html|sh)$/.test(n) && /\/Users\/[a-z]+|\/home\/[a-z]+\//.test(readFileSync(f, 'utf8')))
        mal(f, 'ruta absoluta de una máquina')
    }
  }
}

const cat = leer(join(RAIZ, '.claude-plugin/marketplace.json'))
claudeValidate(RAIZ)
for (const e of cat.plugins) {
  const dir = join(RAIZ, e.source)
  const pj = join(dir, '.claude-plugin/plugin.json')
  if (!existsSync(pj)) { mal(dir, 'falta .claude-plugin/plugin.json'); continue }
  const man = leer(pj)
  if (man.name !== e.name) mal(pj, `name «${man.name}» ≠ entrada del catálogo «${e.name}» (Claude Code no la encontraría)`)
  if (!man.version) mal(pj, 'version fija en plugin.json (estilo pinned: se sube en cada versión)')
  if (e.version) mal(join(RAIZ, '.claude-plugin/marketplace.json'), `${e.name}: la versión vive solo en plugin.json`)
  claudeValidate(dir)
  const aj = join(dir, 'arbrain.json')
  if (!existsSync(aj)) mal(dir, 'falta arbrain.json')
  else validarArbrain(dir, leer(aj))
  sinFugas(dir)
}
if (errores.length) { console.error(errores.map(x => '✗ ' + x).join('\n')); process.exit(1) }
console.log(`✓ catálogo «${cat.name}»: ${cat.plugins.length} extensión(es) válidas`)
