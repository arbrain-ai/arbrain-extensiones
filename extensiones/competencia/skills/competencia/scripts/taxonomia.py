"""Los modelos de negocio de un canal según la taxonomía del dueño (`<carpeta>/taxonomia.json`). Misma regla que el
panel (`panel/index.html`, bloque `logica`): la prueba de paridad corre las dos sobre las mismas fichas.
"""
from __future__ import annotations

import comun


def cargar() -> dict:
    t = comun.leer(comun.carpeta() / 'taxonomia.json')
    return t or comun.leer(comun.extension() / 'references' / 'taxonomia-por-defecto.json')


def _faltan(dueno, base, ruta=''):
    """Llaves que trae la taxonomía por defecto y la del dueño no (solo diccionarios; listas y valores son suyos)."""
    out = []
    for k, v in base.items():
        if k in ('copiada',):
            continue
        if k not in dueno:
            out.append(ruta + k)
        elif isinstance(v, dict) and isinstance(dueno[k], dict):
            out += _faltan(dueno[k], v, ruta + k + '.')
    return out


def por_completar() -> list[str]:
    t = comun.leer(comun.carpeta() / 'taxonomia.json')
    return _faltan(t, comun.leer(comun.extension() / 'references' / 'taxonomia-por-defecto.json')) if t else []


def completar() -> list[str]:
    """Agrega a la taxonomía del dueño lo nuevo de la versión instalada, sin tocar nada de lo que ya tiene (sus modelos,
    nombres y umbrales se quedan como él los dejó)."""
    ruta = comun.carpeta() / 'taxonomia.json'
    t, base = comun.leer(ruta), comun.leer(comun.extension() / 'references' / 'taxonomia-por-defecto.json')
    agregadas = _faltan(t, base)
    for k in agregadas:
        partes, a, b = k.split('.'), t, base
        for x in partes[:-1]:
            a, b = a[x], b[x]
        a[partes[-1]] = b[partes[-1]]
    if agregadas:
        comun.escribir(ruta, t)
    return agregadas


def precio_alto(p, umbral: dict) -> bool:
    if not p or not isinstance(p.get('monto'), (int, float)):
        return False
    r = p.get('recurrencia')
    u = {**umbral, **((umbral.get('por_moneda') or {}).get(str(p.get('moneda') or '').upper()) or {})}
    tope = u.get('mensual', 500) if r == 'mensual' else u.get('trimestral', 300) if r == 'trimestral' else u.get('otro', 1000)
    return p['monto'] >= tope


def modelos_de(f: dict, tax: dict) -> list[str]:
    tiene = set()
    vehiculos = set(f.get('vehiculo') or [])
    destinos = f.get('destinos_video') or []
    caro = any(precio_alto(o.get('precio'), tax.get('alto_ticket', {})) for o in f.get('oferta_pagada') or [])
    for m in tax['modelos']:
        if vehiculos & set(m.get('vehiculos', [])) or any(d.get('rol') in m.get('roles', []) for d in destinos):
            tiene.add(m['id'])
        rr = m.get('rol_repetido')
        if rr and any(d.get('rol') == rr['rol'] and (d.get('en_videos') or 0) >= rr.get('min_videos', 3) for d in destinos):
            tiene.add(m['id'])
        if m.get('por_precio') and caro:
            tiene.add(m['id'])
    return [m['id'] for m in tax['modelos'] if m['id'] in tiene]


def conteo(fichas: list[dict], tax: dict) -> list[dict]:
    out = []
    for m in tax['modelos']:
        k = sum(m['id'] in modelos_de(f, tax) for f in fichas)
        if k:
            out.append({'id': m['id'], 'nombre': m['nombre'], 'canales': k})
    return sorted(out, key=lambda x: -x['canales'])
