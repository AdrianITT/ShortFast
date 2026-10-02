#!/usr/bin/env python3
"""
generar_guia.py — Convierte guia_borrador.json (el JSON que te da el LLM, con
CLAVES en vez de nombres de archivo) en el guia.json final, buscando los
archivos reales del proyecto por clave. Ver prompt_guia.md para el prompt que
genera el borrador.

  "imagenes": ["2A"]   → imagenes/IMG_02A_<lo-que-sea>.jpg  (la más nueva si hay varias)
  "voz": "02a"         → voz/02a_<lo-que-sea>.mp3
  "imagenes": ["LOGO"] → imagenes/*logo*
  "voz": "OUTRO"       → voz/*suscrib* (o la que sobre)
  musica.archivo: "MUSICA" → el único archivo en musica/
  fuentes: se arman solas desde fuentes/ (bold/black/serif)

Uso CLI (dentro del contenedor, junto a render.py):
  docker exec ffmpeg-api python /app/generar_guia.py short_15_legado
  docker exec ffmpeg-api python /app/generar_guia.py short_15_legado --dry

Lee:    <proyecto>/guia_borrador.json
Genera: <proyecto>/guia.json
Uso en FastAPI (main.py), igual que /revisar/{proyecto}:
  from generar_guia import generar
  r = generar(carpeta_proyecto("short_15_legado"))  # {"ok": bool, "guia": {...}, "avisos": [...]}
"""
import json
import os
import re
import sys
from pathlib import Path

PROYECTOS = os.environ.get("PROYECTOS", "/data/proyectos")
NOMBRES_FUENTES = {"bold": "Montserrat-Bold.ttf", "black": "Montserrat-Black.ttf"}
EXT_IMG = {".jpg", ".jpeg", ".png", ".webp"}
EXT_AUD = {".mp3", ".wav", ".m4a", ".ogg"}


def mas_nuevo(archivos):
    return max(archivos, key=lambda p: p.stat().st_mtime) if archivos else None


class Archivos:
    def __init__(self, raiz: Path):
        self.raiz = raiz
        ls = lambda d, ext: sorted(p for p in (raiz / d).glob("*") if p.suffix.lower() in ext) \
            if (raiz / d).is_dir() else []
        self.imagenes = ls("imagenes", EXT_IMG)
        self.voces = ls("voz", EXT_AUD)
        self.musicas = ls("musica", EXT_AUD)
        self.usadas = set()

    def rel(self, p):
        if p:
            self.usadas.add(p)
            return str(p.relative_to(self.raiz)).replace("\\", "/")
        return None

    def imagen(self, clave: str):
        nombre = Path(str(clave)).name  # por si viene con ruta, ej. "imagenes/IMG_01.jpg"
        if "logo" in nombre.lower():
            return mas_nuevo([p for p in self.imagenes if "logo" in p.name.lower()])
        base = Path(nombre).stem  # quita la extensión si trae una (".jpg")
        m = re.search(r"IMG_0*(\d+)([A-Za-z]?)(?![A-Za-z])", base, re.I) or re.search(r"(\d+)([A-Za-z]?)$", base)  # acepta nombres completos
        if not m:
            return None
        num, letra = int(m.group(1)), m.group(2).upper()
        pat = re.compile(r"IMG_0*(\d+)([A-Za-z]?)(?:[_\-.]|$)", re.I)
        cand = [p for p in self.imagenes
                if (mm := pat.match(p.name)) and int(mm.group(1)) == num and mm.group(2).upper() == letra]
        return mas_nuevo(cand)

    def voz(self, clave):
        if clave is None:
            return None
        if str(clave).upper() == "OUTRO":
            libres = [p for p in self.voces if p not in self.usadas]
            fijo = [p for p in libres if "em_santa" in p.name.lower()]  # el audio fijo de la plantilla
            pref = fijo or [p for p in libres if "suscrib" in p.name.lower()]
            return mas_nuevo(pref or libres)
        nombre = Path(str(clave)).name  # por si viene con ruta, ej. "voz/02a_rencor.mp3"
        stem = Path(nombre).stem.lower()  # quita la extensión
        m = re.match(r"^(\d+[a-z]?)", stem)  # se queda solo con el prefijo "02a"
        clave_real = m.group(1) if m else stem
        cand = [p for p in self.voces
                if p.stem.lower() == clave_real or p.stem.lower().startswith(clave_real + "_")]
        return mas_nuevo(cand)

    def musica(self, valor):
        if valor and valor != "MUSICA":
            cand = [p for p in self.musicas if valor.lower() in p.name.lower()]
            return mas_nuevo(cand) or mas_nuevo(self.musicas)
        return mas_nuevo(self.musicas)

    def fuentes(self):
        carpeta = self.raiz / "fuentes"
        todas = sorted(p for p in carpeta.rglob("*") if p.suffix.lower() in (".ttf", ".otf")) \
            if carpeta.is_dir() else []
        buscar = lambda nombre: next((p for p in todas if p.name.lower() == nombre.lower()), None)
        res = {}
        for k, nombre in NOMBRES_FUENTES.items():
            p = buscar(nombre)
            if p:
                res[k] = self.rel(p)
        # la fuente decorativa ("serif") cambia de nombre y formato por proyecto (.ttf u .otf):
        # tomamos la primera que no sea Montserrat.
        serif = next((p for p in todas if "montserrat" not in p.name.lower()), None)
        if serif:
            res["serif"] = self.rel(serif)
        return res


def generar(ruta_proyecto, nombre_borrador="guia_borrador.json", escribir=True, nombre_salida="guia.json"):
    raiz = Path(ruta_proyecto)
    borrador = json.loads((raiz / nombre_borrador).read_text(encoding="utf-8"))
    arch = Archivos(raiz)
    avisos = []

    def marcar(ok, msg):
        if not ok:
            avisos.append(msg)

    escenas = []
    for esc in borrador.get("escenas", []):
        e = dict(esc)  # copia; conservamos todo lo que ya viene del LLM (textos, transiciones, etc.)

        imagenes = []
        for clave in esc.get("imagenes", []):
            img = arch.imagen(str(clave))
            marcar(img, f"Escena {esc.get('id')}: falta imagen para clave '{clave}'")
            if img:
                imagenes.append(arch.rel(img))
        e["imagenes"] = imagenes

        clave_voz = esc.get("voz")
        if any("logo" in Path(str(c)).name.lower() for c in esc.get("imagenes", [])):
            clave_voz = "OUTRO"  # el end card siempre lleva la voz de suscríbete, diga lo que diga el borrador
        voz = arch.voz(clave_voz)
        marcar(voz or clave_voz is None, f"Escena {esc.get('id')}: falta voz para clave '{clave_voz}'")
        e["voz"] = arch.rel(voz)

        escenas.append(e)

    musica_archivo = arch.musica((borrador.get("musica") or {}).get("archivo"))
    marcar(musica_archivo, "No hay música en musica/")

    fuentes = arch.fuentes()
    for k in ("bold", "black", "serif"):
        marcar(k in fuentes, f"No encontré la fuente '{k}' en fuentes/")

    guia = {**borrador, "fuentes": fuentes, "escenas": escenas}
    guia["musica"] = {**borrador.get("musica", {}), "archivo": arch.rel(musica_archivo)}

    sobrantes = [p.name for p in arch.imagenes + arch.voces if p not in arch.usadas]
    if sobrantes:
        avisos.append("Archivos sin usar: " + ", ".join(sobrantes))

    ok = not any(a.startswith(("Escena", "No encontré la fuente", "No hay música")) for a in avisos)

    if escribir and ok:
        (raiz / nombre_salida).write_text(json.dumps(guia, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"ok": ok, "guia": guia, "avisos": avisos}


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)
    arg = sys.argv[1]
    ruta = arg if ("/" in arg) else str(Path(PROYECTOS) / arg)
    dry = "--dry" in sys.argv
    r = generar(ruta, escribir=not dry)
    if dry:
        print(json.dumps(r["guia"], ensure_ascii=False, indent=2))
    for a in r["avisos"]:
        print("⚠️ ", a, file=sys.stderr)
    if not r["ok"]:
        print("❌ Faltan archivos o datos — revisa los avisos antes de renderizar", file=sys.stderr)
        sys.exit(1)
    print("✅ guia.json generado" if not dry else "✅ (dry run)", file=sys.stderr)
