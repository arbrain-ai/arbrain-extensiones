"""Alta del dueño: su nicho, sus palabras, su canal y SU universo de competidores (esquema `arbrain.universo-youtube/v1`,
el mismo del cuartel). Nada entra al universo sin la marca del dueño: `buscar` solo propone candidatos.
"""
from __future__ import annotations

import collections

import comun
import youtube

ESQUEMA_UNIVERSO = 'arbrain.universo-youtube/v1'
CAPAS = [
    {'id': 'propio', 'nombre': 'Tu canal', 'que_es': 'El canal del dueño: la vara contra la que se compara.'},
    {'id': 'competencia', 'nombre': 'Competencia', 'que_es': 'Le hablan a la misma gente con una oferta parecida.'},
    {'id': 'referente', 'nombre': 'Referentes', 'que_es': 'No compiten con él, pero hacen algo que conviene estudiar.'},
]
MARCAS = ('competencia', 'referente', 'ninguno')


def ruta_universo():
    return comun.carpeta() / 'universo.json'


def universo(obligatorio: bool = True) -> dict:
    u = comun.leer(ruta_universo())
    if u is None and obligatorio:
        raise comun.Falta('no hay alta todavía: corre `alta --nicho "…" --palabras "…"`')
    return u


def guardar(u: dict):
    u['actualizado'] = comun.hoy()
    u['resumen'] = {c: sum(c in (x.get('capas') or []) for x in u['canales']) for c in ('propio', 'competencia', 'referente')}
    comun.escribir(ruta_universo(), u)


def taxonomia_inicial():
    """La taxonomía del dueño: si no existe, la por defecto de la extensión (los 7 modelos), que luego edita a su gusto."""
    destino = comun.carpeta() / 'taxonomia.json'
    if not destino.exists():
        base = comun.leer(comun.extension() / 'references' / 'taxonomia-por-defecto.json')
        base['copiada'] = comun.hoy()
        comun.escribir(destino, base)
    return destino


def alta(nicho: str, palabras: list[str], idiomas: list[str], pais: str | None, canal: str | None, cuota_diaria: int | None):
    if not nicho.strip() or not palabras:
        raise comun.Falta('el nicho (en sus palabras) y al menos una palabra de búsqueda')
    u = universo(obligatorio=False) or {
        'esquema': ESQUEMA_UNIVERSO, 'version': 1, 'creado': comun.hoy(),
        'para_que': 'A quién mira la extensión Competencia: el canal del dueño, sus competidores y sus referentes, con ids '
                    'verificados por la YouTube Data API, y las búsquedas para descubrir canales nuevos de su nicho.',
        'reglas': ['Un canal entra solo con la marca del dueño (competencia o referente); los candidatos son propuestas.',
                   'Ids y suscriptores salen de channels.list; nada se escribe a mano.'],
        'capas': CAPAS, 'canales': [], 'ignorados': [], 'consultas': []}
    u['dueno'] = {'nicho': nicho.strip(), 'palabras': palabras, 'idiomas': idiomas or ['es'], 'pais': pais,
                  'canal': None}
    u['cuota_diaria'] = cuota_diaria or u.get('cuota_diaria') or comun.TOPE_POR_DEFECTO
    hechas = {c['q'].lower() for c in u['consultas']}
    for p in palabras:
        for idi in idiomas or ['es']:
            if p.lower() not in hechas:
                u['consultas'].append({'id': comun.slug(f'{p}-{idi}'), 'q': p, 'idioma': idi, 'region': pais, 'activo': True,
                                       'ventana_dias': 180, 'por_que': 'Palabra del dueño en el alta.'})
                hechas.add(p.lower())
    guardar(u)
    taxonomia_inicial()
    if canal:
        marcar_canal(canal, 'propio', motivo='Su canal (lo dio en el alta).')
        u = universo()
    return u


def _entrada(c: dict, capa: str, motivo: str, idioma: str | None) -> dict:
    s = comun.slug(c['nombre'] or c['channel_id'])
    return {'slug': s, 'channel_id': c['channel_id'], 'nombre': c['nombre'], 'handle': c.get('handle'),
            'idioma': idioma or c.get('idioma') or None, 'capa': capa, 'capas': [capa],
            'url': f"https://www.youtube.com/channel/{c['channel_id']}", 'lista_largos': 'UULF' + c['channel_id'][2:],
            'suscriptores': c.get('suscriptores'), 'videos_total': c.get('videos_total'), 'pais': c.get('pais'),
            'miniatura_url': c.get('miniatura_url'), 'motivo': motivo,
            'verificado': {'fecha': comun.hoy(), 'metodo': 'channels.list de la YouTube Data API (llave del dueño)'}}


def marcar_canal(ref: str, capa: str, motivo: str | None = None, idioma: str | None = None) -> dict:
    """Pone un canal en el universo con la capa que dijo el dueño (o lo manda a ignorados con `ninguno`).
    `ref` = id UC…, @handle, URL o el slug de un candidato."""
    if capa not in (*MARCAS, 'propio'):
        raise comun.Falta(f'capa: una de {", ".join(MARCAS)}')
    u = universo()
    cands = {c['slug']: c for c in (comun.leer(comun.carpeta() / 'candidatos.json', {}) or {}).get('candidatos', [])}
    c = cands.get(ref)
    if c is None:
        cuota = comun.Cuota(u.get('cuota_diaria'))
        c = youtube.canal_por(ref, cuota)
        if not c:
            raise comun.Falta(f'no encontré el canal «{ref}» en YouTube (revisa el @handle o pega la URL del canal)')
    cid = c['channel_id']
    u['canales'] = [x for x in u['canales'] if x['channel_id'] != cid]
    u['ignorados'] = [x for x in u['ignorados'] if x['channel_id'] != cid]
    if capa == 'ninguno':
        u['ignorados'].append({'channel_id': cid, 'nombre': c['nombre'], 'fecha': comun.hoy()})
        e = None
    else:
        e = _entrada(c, capa, motivo or ('Candidato de la búsqueda, marcado por el dueño.' if ref in cands else 'Lo nombró el dueño.'),
                     idioma or c.get('idioma') or (u.get('dueno', {}).get('idiomas') or [None])[0])
        usados = {x['slug'] for x in u['canales']}
        while e['slug'] in usados:
            e['slug'] += '-2'
        u['canales'].append(e)
        if capa == 'propio':
            u['dueno']['canal'] = cid
    guardar(u)
    return e or {'channel_id': cid, 'nombre': c['nombre'], 'capa': 'ninguno'}


def buscar(por_consulta: int = 25, consultas: list[str] | None = None) -> dict:
    """Corre las consultas activas (100 unidades cada una), agrupa los videos por canal y propone candidatos que aún no
    están en el universo ni en ignorados, con suscriptores y su último video del tema. No marca a nadie."""
    u = universo()
    cuota = comun.Cuota(u.get('cuota_diaria'))
    vistos = {c['channel_id'] for c in u['canales']} | {c['channel_id'] for c in u['ignorados']}
    apar, ejemplo, idioma_de = collections.Counter(), {}, {}
    corridas = []
    for q in u['consultas']:
        if not q.get('activo', True) or (consultas and q['id'] not in consultas):
            continue
        vs = youtube.buscar_videos(q['q'], cuota, idioma=q.get('idioma'), region=q.get('region'),
                                   dias=q.get('ventana_dias', 180), n=por_consulta)
        corridas.append({'consulta': q['id'], 'q': q['q'], 'videos': len(vs)})
        for v in vs:
            if v['channel_id'] in vistos:
                continue
            apar[v['channel_id']] += 1
            ejemplo.setdefault(v['channel_id'], v)
            idioma_de.setdefault(v['channel_id'], q.get('idioma'))
    info = youtube.canales(list(apar), cuota) if apar else {}
    cands = []
    for cid, k in apar.most_common():
        c = info.get(cid) or {'channel_id': cid, 'nombre': ejemplo[cid]['canal']}
        c.update({'slug': comun.slug(c.get('nombre') or cid), 'apariciones': k, 'idioma': c.get('idioma') or idioma_de[cid],
                  'video_ejemplo': {'titulo': ejemplo[cid]['titulo'], 'publicado': ejemplo[cid]['publicado'],
                                    'url': f"https://www.youtube.com/watch?v={ejemplo[cid]['video_id']}"}})
        cands.append(c)
    cands.sort(key=lambda c: (-c['apariciones'], -(c.get('suscriptores') or 0)))
    out = {'esquema': 'arbrain.competencia.candidatos/v1', 'generado': comun.ahora(), 'nicho': u['dueno']['nicho'],
           'consultas': corridas, 'unidades_hoy': cuota.usadas, 'candidatos': cands}
    comun.escribir(comun.carpeta() / 'candidatos.json', out)
    return out
