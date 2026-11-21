#!/usr/bin/env python3
"""Competencia: el censo propio del dueño sobre los canales de YouTube de su nicho (extensión «Competencia» de Arbrain).

    C=".../skills/competencia/scripts/competencia.py"     # corre desde la carpeta de tu cerebro de Arbrain
    python3 $C alta --nicho "nutriólogos en México" --palabras "nutrióloga, plan de alimentación" [--canal @mio] [--idiomas es] [--pais MX]
    python3 $C buscar [--por-consulta 25]           # propone candidatos (100 unidades por consulta); no marca a nadie
    python3 $C candidatos                           # la lista para que el dueño marque
    python3 $C marcar <slug|@handle|URL|UC…> --capa competencia|referente|ninguno
    python3 $C censo [--n 5] [--subs 2] [--canales a,b] [--sin-resolver]
    python3 $C ver <slug>                           # lo que dejó el censo de un canal (para curar su ficha)
    python3 $C cita <video_id> [--desde M:SS --hasta M:SS]   # subtítulos con minuto
    python3 $C paginas --sugeridas | --abrir-sugeridas | --slug s --clave k --url https://…
    python3 $C construir [--seco]                   # fichas curadas + censo → embudos.json (pasa el validador o no escribe)
    python3 $C validar [embudos.json]
    python3 $C pendientes                           # qué canal falta censar o curar
    python3 $C estudio                              # la tarea semanal: re-censa, compara y escribe qué cambió
    python3 $C estado                               # una línea por pieza: lo que hay y lo que falta
    python3 $C taxonomia [--completar]              # sus modelos; --completar agrega lo nuevo de la versión sin tocar lo suyo
    python3 $C llave < archivo                      # guarda la llave de YouTube (de la entrada estándar; nunca la imprime)

Dónde: lo del dueño en `.claude/memory/extensiones/competencia/`; lo regenerable en ${CLAUDE_PLUGIN_DATA}.
Códigos: 0 bien · 1 error · 2 falta algo o la evidencia no respalda una ficha · 4 falta la llave · 5 tope de cuota.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import alta  # noqa: E402
import censo  # noqa: E402
import comun  # noqa: E402
import estudio  # noqa: E402
import fichas  # noqa: E402
import paginas  # noqa: E402
import taxonomia  # noqa: E402
import validar  # noqa: E402
import youtube  # noqa: E402


def _lista(t: str | None) -> list[str]:
    return [x.strip() for x in (t or '').split(',') if x.strip()]


def cmd_estado(_a):
    c = comun.carpeta()
    u = alta.universo(obligatorio=False)
    if not u:
        print(json.dumps({'alta': False, 'siguiente': 'alta --nicho … --palabras …'}, ensure_ascii=False))
        return 0
    emb = comun.leer(c / 'embudos.json', {}) or {}
    cs, _ = censo.censo_fusionado()
    cuota = comun.Cuota(u.get('cuota_diaria'))
    try:
        comun.llave()
        llave = True
    except comun.SinLlave:
        llave = False
    tax = taxonomia.cargar()
    ya = {x['channel_id'] for x in u['canales']} | {x['channel_id'] for x in u['ignorados']}
    out = {'alta': True, 'nicho': u['dueno']['nicho'], 'canal_propio': bool(u['dueno'].get('canal')),
           'universo': u.get('resumen'), 'candidatos_sin_marcar': sum(x['channel_id'] not in ya for x in (comun.leer(c / 'candidatos.json', {}) or {}).get('candidatos', [])),
           'censados': sum(bool(x.get('videos')) for x in cs.values()), 'fichas': (emb.get('cobertura') or {}).get('fichas', 0),
           'completas': (emb.get('cobertura') or {}).get('completas', 0), 'corte': emb.get('corte'),
           'modelos': taxonomia.conteo(emb.get('fichas', []), tax), 'taxonomia_por_completar': taxonomia.por_completar(),
           'llave_youtube': llave,
           'cuota_hoy': {'usadas': cuota.usadas, 'tope': cuota.tope}, 'yt_dlp': youtube.hay_ytdlp()}
    print(json.dumps(out, ensure_ascii=False, indent=1))
    return 0


def cmd_alta(a):
    u = alta.alta(a.nicho, _lista(a.palabras), _lista(a.idiomas) or ['es'], a.pais, a.canal, a.cuota)
    print(f"Alta lista: nicho «{u['dueno']['nicho']}», {len(u['consultas'])} búsquedas, {len(u['canales'])} canales. "
          f"Datos en {comun.rel(alta.ruta_universo().parent)}/")
    return 0


def cmd_buscar(a):
    r = alta.buscar(a.por_consulta, _lista(a.consultas) or None)
    print(f"{len(r['candidatos'])} candidatos de {len(r['consultas'])} búsquedas ({r['unidades_hoy']} unidades hoy).")
    return cmd_candidatos(a)


def cmd_candidatos(_a):
    r = comun.leer(comun.carpeta() / 'candidatos.json', {}) or {}
    u = alta.universo()
    ya = {c['channel_id'] for c in u['canales']} | {c['channel_id'] for c in u['ignorados']}
    for c in [x for x in r.get('candidatos', []) if x['channel_id'] not in ya]:
        subs = f"{c['suscriptores']:,}" if c.get('suscriptores') is not None else 'oculto'
        print(f"  {c['slug']:<32} {subs:>11} subs · {c['apariciones']}× · {c.get('idioma') or '?'} · «{(c['video_ejemplo']['titulo'] or '')[:60]}»")
    return 0


def cmd_marcar(a):
    e = alta.marcar_canal(a.ref, a.capa, a.motivo, a.idioma)
    print(f"{e['nombre']} → {e['capa']}" + (f" ({e['slug']})" if e.get('slug') else ''))
    return 0


def cmd_censo(a):
    censo.censar(n=a.n, subs=a.subs, resolver_enlaces=not a.sin_resolver, quiero=set(_lista(a.canales)) or None)
    return 0


def cmd_ver(a):
    cs, de = censo.censo_fusionado()
    c = cs.get(a.slug)
    if not c:
        raise comun.Falta(f'«{a.slug}» no tiene censo todavía')
    print(f"# {c['nombre']} · {len(c['videos'])} videos · {de[a.slug]}")
    for d in c['resumen']['dominios'][:12]:
        print(f"  {d['dominio']:<34} en {d['en_videos']} · {d['categoria']:<11} «{d['linea'][:60]}» {d['ejemplo'][:70]}")
    for v in c['videos']:
        t = v.get('cta_hablado', {})
        print(f"\n## {v['publicado']} {v['id']} «{(v['titulo'] or '')[:70]}» · {t.get('transcript')}")
        if t.get('cierre'):
            print(f"   cierre desde {t['cierre_desde']}: {t['cierre'][:300]}")
        for m in t.get('menciones', [])[:8]:
            print(f"   {m['min']:>6} {m['texto'][:110]}")
    return 0


def cmd_cita(a):
    segs, fuente = youtube.subtitulos(a.video, None)
    if not segs:
        raise comun.Falta(f'{a.video}: {fuente}')
    d = fichas._s(a.desde) if a.desde else 0
    h = fichas._s(a.hasta) if a.hasta else 10 ** 9
    print(f'# {a.video} · {fuente}')
    for s, t in segs:
        if d <= s <= h:
            print(f'{s // 60}:{s % 60:02d}  {t}')
    return 0


def cmd_paginas(a):
    if a.sugeridas or a.abrir_sugeridas:
        sug = paginas.sugeridas(a.por_canal, set(_lista(a.canales)) or None)
        if a.sugeridas:
            for p in sug:
                print(f"  {p['slug']:<30} {p['clave']:<20} en {p['en_videos']} videos · {p['categoria']:<10} {p['url'][:90]}")
            return 0
        pedir = [{k: p[k] for k in ('slug', 'clave', 'url')} for p in sug]
    elif a.lista:
        pedir = comun.leer(Path(a.lista))
    elif a.slug and a.clave and a.url:
        pedir = [{'slug': a.slug, 'clave': a.clave, 'url': a.url}]
    else:
        raise comun.Falta('di qué abrir: --sugeridas, --abrir-sugeridas, --lista archivo.json o --slug/--clave/--url')
    for x in paginas.abrir_todas(pedir):
        precios = ', '.join(p['precio'] for p in x.get('precios_en_texto', [])[:5])
        print(f"  {x['slug']}/{x['clave']} {x.get('http')} «{(x.get('titulo') or '')[:60]}» {('· ' + precios) if precios else ''}")
    return 0


def cmd_construir(a):
    out = fichas.construir(seco=a.seco)
    print(f"embudos.json{' (seco: no se escribió)' if a.seco else ''}: {out['cobertura']['fichas']} fichas, "
          f"{out['cobertura']['completas']} completas · VÁLIDO")
    for f in out['fichas']:
        print(f"  {f['slug']:<32} {f['cobertura']['estado']:<9} {', '.join(f['cobertura']['faltan'])}")
    return 0


def cmd_validar(a):
    ruta = Path(a.ruta) if a.ruta else comun.carpeta() / 'embudos.json'
    d = comun.leer(ruta)
    if d is None:
        raise comun.Falta(f'no existe {comun.rel(ruta)}: corre `construir`')
    errores = validar.validar(d)
    if errores:
        print(f'INVÁLIDO · {len(errores)} errores')
        for e in errores:
            print('  ·', e)
        return 1
    n = len(d['fichas'])
    comp = d['cobertura']['completas']
    print(f'VÁLIDO · {n} fichas ({comp} completas, {n - comp} parciales) · {len(d["lo_que_se_repite"])} líneas de «lo que se repite»')
    return 0


def cmd_pendientes(_a):
    for p in fichas.pendientes():
        estado = 'sin censo' if not p['censo'] else 'sin ficha' if not p['ficha'] else ('completa' if p['faltan'] == [] else
                                                                                         f"faltan: {', '.join(p['faltan'] or ['construir'])}")
        print(f"  {p['slug']:<32} {estado}{'' if p['paginas_abiertas'] else ' · sin páginas abiertas'}")
    return 0


def cmd_estudio(a):
    estudio.estudiar(n=a.n, subs=a.subs)
    return 0


def cmd_taxonomia(a):
    if a.completar:
        agregadas = taxonomia.completar()
        print('Taxonomía al día' if not agregadas else f"Agregué a tu taxonomía (sin tocar lo tuyo): {', '.join(agregadas)}")
        return 0
    t = taxonomia.cargar()
    for m in t['modelos']:
        print(f"  {m['id']:<18} {m['nombre']:<24} vehículos: {', '.join(m.get('vehiculos', []))}")
    faltan = taxonomia.por_completar()
    if faltan:
        print(f"  (la versión instalada trae llaves nuevas: {', '.join(faltan)} → `taxonomia --completar`)")
    return 0


def cmd_llave(_a):
    v = sys.stdin.read().strip()
    if not v or len(v) < 20 or any(ch.isspace() for ch in v):
        raise comun.Falta('no recibí una llave válida por la entrada estándar')
    f = comun.guardar_llave(v)
    print(f'Llave guardada (permisos 0600) en {f.name}; no se imprime ni entra al cerebro.')
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog='competencia', description=__doc__.split('\n')[0])
    sub = ap.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('alta')
    s.add_argument('--nicho', required=True)
    s.add_argument('--palabras', required=True, help='separadas por comas, como las buscaría su cliente')
    s.add_argument('--idiomas', default='es')
    s.add_argument('--pais')
    s.add_argument('--canal')
    s.add_argument('--cuota', type=int, help='tope de unidades de YouTube por día (por omisión 2,000 de 10,000)')
    s = sub.add_parser('buscar')
    s.add_argument('--por-consulta', type=int, default=25)
    s.add_argument('--consultas')
    sub.add_parser('candidatos')
    s = sub.add_parser('marcar')
    s.add_argument('ref')
    s.add_argument('--capa', required=True, choices=alta.MARCAS)
    s.add_argument('--motivo')
    s.add_argument('--idioma')
    s = sub.add_parser('censo')
    s.add_argument('--n', type=int, default=5)
    s.add_argument('--subs', type=int, default=2)
    s.add_argument('--canales')
    s.add_argument('--sin-resolver', action='store_true')
    s = sub.add_parser('ver')
    s.add_argument('slug')
    s = sub.add_parser('cita')
    s.add_argument('video')
    s.add_argument('--desde')
    s.add_argument('--hasta')
    s = sub.add_parser('paginas')
    s.add_argument('--sugeridas', action='store_true')
    s.add_argument('--abrir-sugeridas', action='store_true')
    s.add_argument('--por-canal', type=int, default=3)
    s.add_argument('--canales')
    s.add_argument('--lista')
    s.add_argument('--slug')
    s.add_argument('--clave')
    s.add_argument('--url')
    s = sub.add_parser('construir')
    s.add_argument('--seco', action='store_true')
    s = sub.add_parser('validar')
    s.add_argument('ruta', nargs='?')
    sub.add_parser('pendientes')
    s = sub.add_parser('estudio')
    s.add_argument('--n', type=int, default=5)
    s.add_argument('--subs', type=int, default=1)
    sub.add_parser('estado')
    s = sub.add_parser('taxonomia')
    s.add_argument('--completar', action='store_true')
    sub.add_parser('llave')
    a = ap.parse_args(argv)
    try:
        return globals()['cmd_' + a.cmd](a)
    except (comun.Falta, fichas.Curaduria) as e:
        print(f'falta: {e}', file=sys.stderr)
        return 2
    except comun.SinLlave as e:
        print(f'sin_llave: {e}', file=sys.stderr)
        return 4
    except comun.TopeCuota as e:
        print(f'tope_cuota: {e}', file=sys.stderr)
        return 5


if __name__ == '__main__':
    sys.exit(main())
