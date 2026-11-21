"""El validador de `embudos.json` (esquema `competidores-embudos/v1`, `references/esquema.md`). Es la puerta: lo que no
pasa no llega al panel. Sin dependencias.

Además de tipos y campos obligatorios comprueba las reglas de evidencia: todo `dato` lleva fuente, fecha AAAA-MM-DD y
un nivel permitido; un precio solo cuenta como visto con nivel `precio_visto` o `archivo_wayback`; una cita hablada
lleva nivel `dicho_en_video` y minuto M:SS; un campo vacío exige su `<campo>_estado` (vacío no es cero); la cobertura
declarada coincide con la calculada; ninguna fuente es una ruta absoluta de una máquina.
Compatible con el archivo del autor de la extensión (de ahí viene el esquema): `lo_que_se_repite` admite de 0 a 8 líneas.
"""
from __future__ import annotations

import re

NIVELES = {'enlace_visible', 'pagina_abierta', 'precio_visto', 'dicho_en_video', 'archivo_wayback', 'heredado'}
CAMPOS = ['destinos_video', 'cta_hablado', 'regalo_entrada', 'oferta_pagada', 'promesa', 'vehiculo', 'mecanismo']
RECURRENCIAS = {'mensual', 'trimestral', 'anual', 'pago_unico', None}
FECHA = re.compile(r'^\d{4}-\d{2}-\d{2}$')
ABSOLUTA = re.compile(r'(^|[\s(])(/(Users|home)/|[A-Z]:\\(Users)\\)')


class Validador:
    def __init__(self):
        self.errores: list[str] = []

    def err(self, ruta, msg):
        self.errores.append(f'{ruta}: {msg}')

    def tipo(self, x, t, ruta):
        if not isinstance(x, t):
            self.err(ruta, f'se esperaba {getattr(t, "__name__", t)}, hay {type(x).__name__}')
            return False
        return True

    def req(self, obj, claves, ruta):
        if not isinstance(obj, dict):
            self.err(ruta, 'se esperaba un objeto')
            return
        for k in claves:
            if k not in obj:
                self.err(ruta, f'falta «{k}»')

    def dato(self, d, ruta):
        if not self.tipo(d, dict, ruta):
            return
        self.req(d, ['fuente', 'fecha', 'nivel'], ruta)
        if not d.get('fuente'):
            self.err(ruta, 'fuente vacía')
        for k in ('fuente', 'respaldo', 'nota'):
            if isinstance(d.get(k), str) and ABSOLUTA.search(d[k]):
                self.err(ruta, f'{k} con ruta absoluta de una máquina (cítala relativa al cerebro o como $DATOS/…)')
        if not FECHA.match(str(d.get('fecha', ''))):
            self.err(ruta, f"fecha no es AAAA-MM-DD: {d.get('fecha')}")
        if d.get('nivel') not in NIVELES:
            self.err(ruta, f"nivel no permitido: {d.get('nivel')}")

    def lista(self, f, campo, ruta, fn):
        xs = f.get(campo)
        if not self.tipo(xs, list, f'{ruta}.{campo}'):
            return
        if not xs and not f.get(f'{campo}_estado'):
            self.err(ruta, f'«{campo}» vacío sin «{campo}_estado» que diga por qué')
        for i, x in enumerate(xs):
            fn(x, f'{ruta}.{campo}[{i}]')

    def destino(self, x, r):
        self.req(x, ['rol', 'url', 'en_videos', 'de_videos', 'dato'], r)
        self.tipo(x.get('en_videos'), int, f'{r}.en_videos')
        if isinstance(x.get('en_videos'), int) and isinstance(x.get('de_videos'), int) and x['en_videos'] > x['de_videos']:
            self.err(r, 'en_videos > de_videos')
        self.dato(x.get('dato'), f'{r}.dato')

    def cta(self, x, r):
        self.req(x, ['video_id', 'minuto', 'cita', 'pide', 'dato'], r)
        if not re.match(r'^\d+:\d{2}$', str(x.get('minuto', ''))):
            self.err(r, f"minuto no es M:SS: {x.get('minuto')}")
        if not x.get('cita'):
            self.err(r, 'cita vacía')
        self.dato(x.get('dato'), f'{r}.dato')
        if (x.get('dato') or {}).get('nivel') != 'dicho_en_video':
            self.err(r, 'una cita hablada debe tener nivel dicho_en_video')

    def regalo(self, x, r):
        self.req(x, ['nombre', 'requiere', 'url', 'dato'], r)
        self.dato(x.get('dato'), f'{r}.dato')

    def oferta(self, x, r):
        self.req(x, ['nombre', 'precio', 'url', 'dato'], r)
        self.dato(x.get('dato'), f'{r}.dato')
        p = x.get('precio')
        if p is not None:
            if self.tipo(p, dict, f'{r}.precio'):
                self.req(p, ['monto', 'moneda', 'recurrencia', 'texto'], f'{r}.precio')
                self.tipo(p.get('monto'), (int, float), f'{r}.precio.monto')
                if p.get('recurrencia') not in RECURRENCIAS:
                    self.err(f'{r}.precio', f"recurrencia no permitida: {p.get('recurrencia')}")
            if (x.get('dato') or {}).get('nivel') not in ('precio_visto', 'archivo_wayback'):
                self.err(r, 'hay precio pero el dato no es precio_visto ni archivo_wayback')

    def promesa(self, x, r):
        self.req(x, ['cita', 'donde', 'dato'], r)
        self.dato(x.get('dato'), f'{r}.dato')

    def ficha(self, f, r, slugs):
        self.req(f, ['slug', 'nombre', 'channel_id', 'idioma', 'motivo', 'muestra', 'cobertura', 'no_visto', *CAMPOS], r)
        if f.get('slug') in slugs:
            self.err(r, f"slug repetido {f.get('slug')}")
        slugs.add(f.get('slug'))
        if not re.match(r'^UC[\w-]{22}$', str(f.get('channel_id', ''))):
            self.err(r, 'channel_id no parece un id de canal')
        self.tipo(f.get('no_visto'), list, f'{r}.no_visto')
        self.req(f.get('muestra') or {}, ['videos', 'con_transcript', 'censo'], f'{r}.muestra')
        self.lista(f, 'destinos_video', r, self.destino)
        self.lista(f, 'cta_hablado', r, self.cta)
        self.lista(f, 'regalo_entrada', r, self.regalo)
        self.lista(f, 'oferta_pagada', r, self.oferta)
        self.lista(f, 'promesa', r, self.promesa)
        if not self.tipo(f.get('vehiculo'), list, f'{r}.vehiculo') or not f.get('vehiculo'):
            self.err(r, 'vehiculo vacío')
        mec = f.get('mecanismo')
        if not mec:
            if not f.get('mecanismo_estado'):
                self.err(r, '«mecanismo» vacío sin «mecanismo_estado» que diga por qué')
        elif self.tipo(mec, dict, f'{r}.mecanismo'):
            self.req(mec, ['texto', 'en_sus_palabras', 'dato'], f'{r}.mecanismo')
            self.dato(mec.get('dato'), f'{r}.mecanismo.dato')
            if mec.get('en_sus_palabras') is False and not mec.get('lectura_de_levy'):
                self.err(f'{r}.mecanismo', 'si no está en sus palabras debe marcarse lectura_de_levy: true')
        faltan = cobertura(f)
        cob = f.get('cobertura') or {}
        esperado = 'completa' if not faltan else 'parcial'
        if cob.get('estado') != esperado or sorted(cob.get('faltan', [])) != sorted(faltan):
            self.err(f'{r}.cobertura', f"declara {cob.get('estado')} {cob.get('faltan')}, calculado {esperado} {faltan}")

    def archivo(self, d) -> list[str]:
        self.req(d, ['esquema', 'version', 'generado', 'corte', 'reglas', 'fuentes_base', 'cobertura', 'lo_que_se_repite', 'fichas'], '$')
        if d.get('esquema') != 'competidores-embudos/v1':
            self.err('$.esquema', f"esperado competidores-embudos/v1, hay {d.get('esquema')}")
        slugs: set = set()
        for i, f in enumerate(d.get('fichas', [])):
            self.ficha(f, f"$.fichas[{i}]({f.get('slug')})", slugs)
        rep = d.get('lo_que_se_repite', [])
        if not isinstance(rep, list) or len(rep) > 8:
            self.err('$.lo_que_se_repite', 'lista de 0 a 8 líneas')
        for i, x in enumerate(rep if isinstance(rep, list) else []):
            r = f'$.lo_que_se_repite[{i}]'
            self.req(x, ['texto', 'respaldo', 'lectura_de_levy'], r)
            for s in x.get('respaldo', []):
                if s not in slugs:
                    self.err(r, f'respaldo «{s}» no es una ficha')
        c = d.get('cobertura', {})
        n = len(d.get('fichas', []))
        comp = sum((f.get('cobertura') or {}).get('estado') == 'completa' for f in d.get('fichas', []))
        if c.get('fichas') != n or c.get('completas') != comp or c.get('parciales') != n - comp:
            self.err('$.cobertura', f'no cuadra con las fichas ({n} fichas, {comp} completas)')
        return self.errores


def cobertura(f: dict) -> list[str]:
    """Lo que le falta a una ficha para ser completa (vacío = completa)."""
    faltan = [c for c in CAMPOS if not f.get(c)]
    ofs = f.get('oferta_pagada') or []
    if ofs and not any(o.get('precio') and (o.get('dato') or {}).get('nivel') in ('precio_visto', 'archivo_wayback') for o in ofs):
        faltan.append('precio_de_la_oferta')
    return faltan


def validar(d: dict) -> list[str]:
    return Validador().archivo(d)


def validar_fichas(fichas: list[dict]) -> list[str]:
    v, vistos = Validador(), set()
    for i, f in enumerate(fichas):
        v.ficha(f, f"fichas[{i}]({f.get('slug')})", vistos)
    return v.errores
