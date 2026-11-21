"""De lo curado a `embudos.json`: une el universo, el censo, las páginas abiertas y las fichas que Levy curó con el
dueño (`<carpeta>/fichas/<slug>.json`), calcula la cobertura y pasa el validador. Lo que no pasa no se escribe.

Una ficha curada solo dice lo que se vio y con qué evidencia; lo mecánico lo pone este script:
  - identidad (nombre, id, handle, idioma, capas) sale del universo;
  - `muestra` y `destinos_video` salen del censo (`roles` asigna el papel de cada enlace en su embudo);
  - `cta_hablado` se pide por minutos (`desde`/`hasta`) y la cita se copia LITERAL de los subtítulos; si no hay texto
    en ese tramo, falla;
  - un `dato` corto `{"pagina": "<clave>"}` se completa con la URL final, el día y el respaldo de la página abierta; si
    la página no abrió, falla. Una promesa citada de una página debe aparecer literal en su texto.
Formato completo y ejemplo: `references/curar-fichas.md` y `references/ficha-ejemplo.json`.
"""
from __future__ import annotations

import re

import alta
import comun
import censo
import paginas
import validar
import youtube

ESQUEMA = 'competidores-embudos/v1'
FUERA_DE_EMBUDO = {'otro_video': 'otro_video', 'afiliado': 'afiliado_o_patrocinio', 'comunidad': 'comunidad',
                   'newsletter': 'newsletter', 'mensajeria': 'canal_whatsapp', 'agenda': 'web_propia'}


class Curaduria(Exception):
    """Una ficha curada pide algo que la evidencia no respalda (código 2)."""


def _norm(t: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[«»"“”‘’\']', '', (t or '').lower())).strip()


def _s(mmss: str) -> int:
    a, b = str(mmss).split(':')
    return int(a) * 60 + int(b)


class Armador:
    def __init__(self):
        self.u = alta.universo()
        self.canales = {c['slug']: c for c in self.u['canales']}
        self.censo, self.censo_de = censo.censo_fusionado()
        self.paginas = paginas.abiertas()
        self.videos = {v['id']: v for c in self.censo.values() for v in c.get('videos', [])}

    # ── datos de evidencia ──
    def dato(self, slug: str, d: dict, ruta: str) -> dict:
        if not isinstance(d, dict):
            raise Curaduria(f'{ruta}: dato debe ser un objeto')
        if 'pagina' in d:
            p = self.paginas.get((slug, d['pagina']))
            if not p:
                raise Curaduria(f'{ruta}: la página «{d["pagina"]}» de {slug} no está abierta (corre `paginas`)')
            if not p.get('http') or p['http'] >= 400:
                raise Curaduria(f'{ruta}: la página «{d["pagina"]}» no abrió ({p.get("http")}); no respalda un dato')
            out = {'fuente': p.get('final') or p['url'], 'fecha': p['abierta'][:10], 'nivel': d.get('nivel', 'pagina_abierta'),
                   'respaldo': p.get('evidencia')}
        elif 'video' in d:
            out = {'fuente': f"https://www.youtube.com/watch?v={d['video']}&t={_s(d.get('minuto', '0:00'))}s",
                   'fecha': comun.hoy(), 'nivel': d.get('nivel', 'dicho_en_video')}
        elif d.get('censo'):
            out = {'fuente': self.censo_de.get(slug) or 'censo', 'fecha': (self.censo.get(slug) or {}).get('corte') or comun.hoy(),
                   'nivel': 'enlace_visible'}
        else:
            out = dict(d)
        if d.get('nota'):
            out['nota'] = d['nota']
        return out

    def texto_pagina(self, slug: str, clave: str) -> str:
        p = self.paginas.get((slug, clave)) or {}
        ev = comun.raiz() / p['evidencia'] if p.get('evidencia') else None
        return ev.read_text(encoding='utf-8') if ev and ev.exists() else ''

    def segs(self, vid: str, idioma: str | None):
        s, fuente = youtube.subtitulos(vid, idioma)
        if not s:
            raise Curaduria(f'{vid}: sin subtítulos guardados ({fuente}); corre el censo con --subs o quita la cita')
        return s, fuente

    # ── piezas ──
    def cta(self, slug: str, x: dict, idioma, ruta) -> dict:
        if not x.get('desde') or not x.get('hasta'):
            raise Curaduria(f'{ruta}: una cita hablada se pide por minutos («desde» y «hasta», M:SS)')
        segs, fuente = self.segs(x['video_id'], idioma)
        trozo = [t for s, t in segs if _s(x['desde']) <= s <= _s(x['hasta'])]
        if not trozo:
            raise Curaduria(f"{ruta}: no hay texto entre {x['desde']} y {x['hasta']} en {x['video_id']}")
        v = self.videos.get(x['video_id'], {})
        return {'video_id': x['video_id'], 'titulo': v.get('titulo'), 'publicado': v.get('publicado'), 'minuto': x['desde'],
                'lugar': x.get('lugar', 'durante'), 'pide': x['pide'],
                'cita': re.sub(r'\s+', ' ', ' '.join(trozo).replace('&nbsp;', ' ')).strip(),
                'dato': {'fuente': f"https://www.youtube.com/watch?v={x['video_id']}&t={_s(x['desde'])}s",
                         'fecha': comun.hoy(), 'nivel': 'dicho_en_video', 'nota': fuente}}

    def promesa(self, slug: str, x: dict, idioma, ruta) -> dict:
        d = x.get('dato') or {}
        if 'pagina' in d and _norm(x['cita']) not in _norm(self.texto_pagina(slug, d['pagina'])):
            raise Curaduria(f'{ruta}: la promesa «{x["cita"][:60]}…» no aparece literal en la página «{d["pagina"]}»')
        if 'video' in d:
            segs, _ = self.segs(d['video'], idioma)
            if _norm(x['cita']) not in _norm(' '.join(t for _, t in segs)):
                raise Curaduria(f'{ruta}: la promesa no aparece literal en los subtítulos de {d["video"]}')
        return {'cita': x['cita'], 'donde': x.get('donde', ''), 'dato': self.dato(slug, d, f'{ruta}.dato')}

    def destinos(self, slug: str, roles: dict, minimo: int) -> list[dict]:
        c = self.censo.get(slug)
        if not c:
            return []
        n, agreg = len(c['videos']), {}
        for v in c['videos']:
            for pos, e in enumerate(v.get('enlaces', [])):
                clave = next((p for p in roles if p in e['url'] or e['dominio'] == p), None) or e['dominio']
                a = agreg.setdefault(clave, {'videos': set(), 'ej': e, 'pos': []})
                a['videos'].add(v['id'])
                a['pos'].append(pos + 1)
        out = []
        for clave, a in sorted(agreg.items(), key=lambda kv: -len(kv[1]['videos'])):
            e = a['ej']
            if clave in roles:
                rol, nombre = (list(roles[clave]) + [None])[:2]
            elif len(a['videos']) >= minimo and e['categoria'] != 'red_social':
                rol, nombre = FUERA_DE_EMBUDO.get(e['categoria'], 'externo'), None
            else:
                continue
            if rol == 'ignorar':
                continue
            dst = e.get('destino') or {}
            out.append({'rol': rol, 'nombre': nombre, 'url': e['url'], 'etiqueta': e['linea'] or None,
                        'en_videos': len(a['videos']), 'de_videos': n, 'posicion_mediana': sorted(a['pos'])[len(a['pos']) // 2],
                        'destino_final': dst.get('final'), 'http': dst.get('http'),
                        'dato': {'fuente': self.censo_de.get(slug), 'fecha': c.get('corte') or comun.hoy(),
                                 'nivel': 'pagina_abierta' if dst.get('http') == 200 else 'enlace_visible',
                                 'nota': f"descripción de {len(a['videos'])} de sus últimos {n} videos largos"
                                         + (f"; destino abierto: «{dst.get('titulo_pagina')}»" if dst.get('titulo_pagina') else '')}})
        return out

    def muestra(self, slug: str) -> dict:
        c = self.censo.get(slug) or {'videos': [], 'resumen': {}}
        fechas = sorted(v['publicado'] for v in c['videos'] if v.get('publicado'))
        return {'videos': len(c['videos']), 'desde': fechas[0] if fechas else None, 'hasta': fechas[-1] if fechas else None,
                'con_transcript': (c.get('resumen') or {}).get('con_transcript', 0),
                'descripciones_de': sorted({v.get('descripcion_de', '?') for v in c['videos']}),
                'censo': self.censo_de.get(slug) or 'sin censo'}

    def ficha(self, cur: dict) -> dict:
        s = cur.get('slug')
        canal = self.canales.get(s)
        if not canal:
            raise Curaduria(f'fichas/{s}.json: «{s}» no está en el universo (márcalo primero)')
        idioma = canal.get('idioma') or (self.censo.get(s) or {}).get('idioma')
        r = f'fichas/{s}.json'
        f = {'slug': s, 'nombre': canal['nombre'], 'channel_id': canal['channel_id'], 'handle': canal.get('handle'),
             'idioma': idioma or 'es', 'capas': canal.get('capas') or [canal.get('capa')],
             'motivo': cur.get('motivo') or canal.get('motivo') or 'Lo marcó el dueño.', 'muestra': self.muestra(s)}
        f['destinos_video'] = self.destinos(s, cur.get('roles') or {}, int(cur.get('minimo_repeticion', 2)))
        f['cta_hablado'] = [self.cta(s, x, idioma, f'{r}.cta_hablado[{i}]') for i, x in enumerate(cur.get('cta_hablado', []))]
        f['regalo_entrada'] = [{**x, 'dato': self.dato(s, x.get('dato'), f'{r}.regalo_entrada[{i}].dato')}
                               for i, x in enumerate(cur.get('regalo_entrada', []))]
        f['oferta_pagada'] = [{**{'precio': None}, **x, 'dato': self.dato(s, x.get('dato'), f'{r}.oferta_pagada[{i}].dato')}
                              for i, x in enumerate(cur.get('oferta_pagada', []))]
        f['promesa'] = [self.promesa(s, x, idioma, f'{r}.promesa[{i}]') for i, x in enumerate(cur.get('promesa', []))]
        f['vehiculo'] = list(dict.fromkeys(cur.get('vehiculo', [])))
        mec = cur.get('mecanismo')
        f['mecanismo'] = {**mec, 'dato': self.dato(s, mec.get('dato'), f'{r}.mecanismo.dato')} if mec else None
        for c in validar.CAMPOS:
            if cur.get(f'{c}_estado'):
                f[f'{c}_estado'] = cur[f'{c}_estado']
        if not f['destinos_video'] and not f.get('destinos_video_estado'):
            f['destinos_video_estado'] = 'no_visto: sus descripciones no traen enlaces repetidos' if self.censo.get(s) else 'no_visto: sin censo'
        f['no_visto'] = cur.get('no_visto', [])
        faltan = validar.cobertura(f)
        f['cobertura'] = {'estado': 'completa' if not faltan else 'parcial', 'faltan': faltan}
        return f


def curadas() -> list[dict]:
    d = comun.carpeta() / 'fichas'
    return [comun.leer(p) for p in sorted(d.glob('*.json'))] if d.exists() else []


def construir(seco: bool = False) -> dict:
    a = Armador()
    fs = [a.ficha(c) for c in curadas()]
    orden = {c['slug']: i for i, c in enumerate(a.u['canales'])}
    fs.sort(key=lambda f: orden.get(f['slug'], 999))
    comp = sum(f['cobertura']['estado'] == 'completa' for f in fs)
    corte = max([c.get('corte') or '' for c in a.censo.values()] + [comun.hoy() if not a.censo else ''])
    out = {
        'esquema': ESQUEMA, 'version': 1, 'generado': comun.ahora(), 'corte': corte or comun.hoy(),
        'que_es': f"El embudo a grandes rasgos de {len(fs)} canales del nicho «{a.u['dueno']['nicho']}»: a dónde manda cada "
                  'video, regalo, oferta pagada con precio, promesa, vehículo y mecanismo; cada dato con fuente, fecha y nivel.',
        'documentado_en': 'extensión competencia › references/esquema.md',
        'reglas': ['Solo páginas públicas: no se registró ningún correo, no se compró, no se envió nada.',
                   'Dato sin fuente no entra; lo que no se pudo ver va en *_estado o no_visto.',
                   'Observación, motivo y precio por separado; nada por analogía entre competidores.',
                   '`lectura_de_levy: true` = interpretación, no observación.'],
        'fuentes_base': {'censo': sorted(set(a.censo_de.values())), 'paginas': '.claude/memory/extensiones/competencia/paginas-abiertas.json',
                         'universo': '.claude/memory/extensiones/competencia/universo.json',
                         'fichas': '.claude/memory/extensiones/competencia/fichas/'},
        'cobertura': {'fichas': len(fs), 'completas': comp, 'parciales': len(fs) - comp,
                      'faltantes': {f['slug']: f['cobertura']['faltan'] for f in fs if f['cobertura']['faltan']}},
        'lo_que_se_repite': comun.leer(comun.carpeta() / 'patrones.json', []) or [],
        'fichas': fs,
    }
    errores = validar.validar(out)
    if errores:
        raise Curaduria('embudos.json no pasa el validador:\n  · ' + '\n  · '.join(errores[:40]))
    if not seco:
        comun.escribir(comun.carpeta() / 'embudos.json', out)
    return out


def pendientes() -> list[dict]:
    """Por canal del universo: si tiene censo, ficha curada y qué le falta. Lo usa Levy para saber qué curar."""
    a = Armador()
    hechas = {c['slug']: c for c in curadas()}
    emb = {f['slug']: f for f in (comun.leer(comun.carpeta() / 'embudos.json', {}) or {}).get('fichas', [])}
    abiertas = {s for s, _ in a.paginas}
    out = []
    for c in censo.objetivo(a.u, None):
        s = c['slug']
        out.append({'slug': s, 'nombre': c['nombre'], 'censo': s in a.censo and bool(a.censo[s].get('videos')),
                    'ficha': s in hechas, 'paginas_abiertas': s in abiertas,
                    'faltan': (emb.get(s) or {}).get('cobertura', {}).get('faltan') if s in emb else None})
    return out
