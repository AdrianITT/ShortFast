"""
Genera el guia.json de un proyecto a partir de su guía en texto (guia.md) usando Gemini.

Flujo: leer guía + lista de archivos + ejemplo → Gemini → revisar/corregir con código → guardar.
"""
import glob
import json
import os
import subprocess
import time
import urllib.error
import urllib.request

W = 1080
EFECTOS = {"zoom_in_lento", "zoom_in", "zoom_out", "paneo_der", "paneo_rapido", "ninguno"}
TRANSICIONES = {"corte", "fade", "fadeblack", "fadewhite", "dissolve"}
POSICIONES = {"centro", "arriba", "abajo", "abajo_firma", "izquierda", "derecha"}
ANIMACIONES = {"ninguna", "golpe", "fade", "palabra_por_palabra"}
FUENTES = {
    "bold": "fuentes/montserrat/Montserrat-Bold.ttf",
    "black": "fuentes/montserrat/Montserrat-Black.ttf",
    "serif": "fuentes/sunmore-slant-free/Sunmore Slant Free.ttf",
}


class ErrorGuia(Exception):
    """Error que se le muestra al usuario tal cual."""
    def __init__(self, mensaje, detalles=None):
        super().__init__(mensaje)
        self.detalles = detalles or []


INSTRUCCIONES = """
Eres un editor de video. Convierte la GUÍA de un YouTube Short en un archivo guia.json
que un programa usa para renderizar el video. Responde SOLO con el JSON, sin explicaciones.

REGLAS DEL FORMATO
1. Una escena por cada archivo de voz, en el orden de la guía. La última escena es el end card.
2. Usa EXACTAMENTE los nombres de archivo de la lista ARCHIVOS DISPONIBLES, con su carpeta
   ("imagenes/...", "voz/...", "musica/..."). Nunca inventes nombres. Relaciona las imágenes
   con la guía por su número (IMG 1 → el archivo que tenga 01 o 1 en el nombre; 2A → 02A, etc.).
   Si falta la imagen de una escena, reutiliza la imagen existente más parecida.
3. Pantallas negras con texto: "imagenes": [] y "fondo": "negro", "efecto": "ninguno".
4. Montaje de varias imágenes con UN solo audio y corte duro entre ellas: pon todas en "imagenes"
   y agrega "segmentos_texto": una lista con el texto exacto de la voz que va con cada imagen,
   en orden (mismo número de elementos que imágenes).
5. Dos imágenes con un solo audio y cross dissolve entre ellas: "reparto_imagenes": "mitades" y
   "transicion_interna": {"tipo": "dissolve", "duracion": 0.5}. Sin segmentos_texto.
6. Si la guía divide la frase final en dos pantallas pero hay un solo audio (dice "continuación"),
   haz UNA escena con los dos textos: el primero con "fin_desde_final" y el segundo con
   "inicio_desde_final" del mismo valor (los segundos que dura la segunda frase al final del audio).
7. End card: última escena con "imagenes": ["imagenes/Logo.png"], "encuadre": "ajustar",
   "efecto": "ninguno", voz "voz/em_santa_Suscribance.mp3" si existe, el CTA de la guía como texto
   (fuente bold, tamano 44-46, posicion "abajo_firma", animacion "ninguna") y "transicion_salida": null.

CAMPOS DE CADA ESCENA
- id: texto ("1", "2"...).
- efecto: zoom_in_lento | zoom_in | zoom_out | paneo_der | paneo_rapido | ninguno.
  "zoom lento" → zoom_in_lento, "zoom a..." → zoom_in, "zoom out" → zoom_out, "paneo" → paneo_der.
- musica_vol: entre 0.10 y 0.50. Sigue el arco de la guía: bajo al inicio (0.15), más bajo en el
  re-hook (0.12), sube hacia el clímax (hasta 0.50), 0.0 en la frase final (silencio), 0.10 en el end card.
- transicion_salida: la transición que va DESPUÉS de esa escena.
  CORTE DURO → {"tipo": "corte"} · fade to black → {"tipo": "fadeblack", "duracion": 0.5 o 1.0}
  FLASH BLANCO → {"tipo": "fadewhite", "duracion": 0.1} · cross dissolve → {"tipo": "dissolve", "duracion": ...}
  fade → {"tipo": "fade", "duracion": 0.5}.
- textos: lista (puede ir vacía). Cada texto:
  contenido, fuente (bold | black | serif), color ("white", "#FFD700" dorado, "#FF3333" rojo,
  "#AAAAAA" gris para firmas), tamano, posicion (centro | arriba | abajo | abajo_firma |
  izquierda | derecha), animacion (ninguna | golpe | fade | palabra_por_palabra) y el momento:
    · "inicio": 0 → aparece desde el inicio (textos "antes que la voz", el hook, frases de golpe).
    · "inicio_desde_final": N → aparece N segundos antes de que termine la voz de la escena.
      Calcula N con ~15 caracteres de voz por segundo (+0.5 s por cada "...") contando desde
      donde se dice esa frase hasta el final del texto de la voz.
    · opcional "fin_desde_final": N o "duracion": N para que desaparezca antes.
  Tamaños: hook/golpes en black 85-120, citas en serif 64-85, firmas "— Autor" en serif gris 50
  con posicion "abajo_firma". Una palabra clave grande sola puede ir a 130-170.
  Las citas "línea por línea" van como varios textos con fade (arriba, centro/abajo, firma) y
  distintos inicio_desde_final.

NIVEL SUPERIOR (cópialo del ejemplo cambiando lo necesario):
proyecto, formato, fuentes, voz_retraso 0.3, pausa_entre_escenas 0.3, duracion_max 90,
musica {"archivo": el archivo de musica/ disponible, "fade_out": 2, "volumen": 0.6}, escenas.
"""


# ─────────────────────────── lectura del proyecto ───────────────────────────

def leer_guia_texto(d):
    for nombre in ("guia.md", "guia.txt", "Guia.md", "GUIA.md"):
        ruta = os.path.join(d, nombre)
        if os.path.isfile(ruta):
            return open(ruta, encoding="utf-8", errors="replace").read()
    otros = sorted(glob.glob(os.path.join(d, "*.md")) + glob.glob(os.path.join(d, "*.txt")))
    if otros:
        return open(otros[0], encoding="utf-8", errors="replace").read()
    raise ErrorGuia("No encuentro la guía. Sube tu guía como guia.md en la carpeta del proyecto.")


def listar(d, sub):
    carpeta = os.path.join(d, sub)
    if not os.path.isdir(carpeta):
        return []
    return sorted(f for f in os.listdir(carpeta) if not f.startswith("."))


def cargar_ejemplo(plantilla, proyectos, excluir):
    ruta = os.path.join(plantilla, "ejemplo_guia.json")
    if os.path.isfile(ruta):
        return open(ruta, encoding="utf-8").read()
    # Si no hay ejemplo en la plantilla, usa la guía más reciente de otro proyecto
    candidatos = [p for p in glob.glob(os.path.join(proyectos, "*", "guia.json"))
                  if os.path.basename(os.path.dirname(p)) != excluir]
    if not candidatos:
        raise ErrorGuia("No hay ningún guia.json de ejemplo. Copia uno a plantilla/ejemplo_guia.json.")
    return open(max(candidatos, key=os.path.getmtime), encoding="utf-8").read()


def armar_prompt(nombre, d, plantilla, proyectos):
    archivos = {sub: listar(d, sub) for sub in ("imagenes", "voz", "musica")}
    lista = "\n".join(f"{sub}/: " + (", ".join(fs) if fs else "(vacío)") for sub, fs in archivos.items())
    return (
        INSTRUCCIONES
        + f"\n\nNOMBRE DEL PROYECTO: {nombre}\n"
        + f"\nARCHIVOS DISPONIBLES:\n{lista}\n"
        + f"\nEJEMPLO DE UN guia.json QUE FUNCIONA (otro Short):\n{cargar_ejemplo(plantilla, proyectos, nombre)}\n"
        + f"\nGUÍA DEL SHORT A CONVERTIR:\n{leer_guia_texto(d)}\n"
    )


# ─────────────────────────── Gemini ───────────────────────────

def llamar_gemini(prompt, key, modelo):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{modelo}:generateContent"
    cuerpo = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"responseMimeType": "application/json", "temperature": 0.2},
    }
    peticion = urllib.request.Request(
        url, data=json.dumps(cuerpo).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "x-goog-api-key": key},
    )
    esperas = [15, 45, 90]  # si Gemini está saturado (503) o limitado (429), reintenta
    for intento in range(len(esperas) + 1):
        try:
            with urllib.request.urlopen(peticion, timeout=240) as r:
                datos = json.loads(r.read().decode("utf-8"))
            break
        except urllib.error.HTTPError as e:
            texto = e.read().decode("utf-8", errors="replace")
            try:
                texto = json.loads(texto)["error"]["message"]
            except Exception:
                pass
            if e.code in (429, 500, 503) and intento < len(esperas):
                time.sleep(esperas[intento])
                continue
            raise ErrorGuia(f"Gemini respondió con error {e.code}: {texto[:300]}")
        except urllib.error.URLError as e:
            raise ErrorGuia(f"No pude conectar con Gemini: {e.reason}")

    try:
        partes = datos["candidates"][0]["content"]["parts"]
        return "".join(p.get("text", "") for p in partes if not p.get("thought"))
    except (KeyError, IndexError):
        razon = datos.get("promptFeedback") or datos.get("candidates", [{}])[0].get("finishReason")
        raise ErrorGuia(f"Gemini no devolvió texto ({razon})")


def extraer_json(texto):
    t = texto.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[1] if "\n" in t else t
        t = t.rsplit("```", 1)[0]
    ini, fin = t.find("{"), t.rfind("}")
    if ini == -1 or fin == -1:
        raise ErrorGuia("La respuesta de la IA no trae un JSON.")
    try:
        return json.loads(t[ini:fin + 1])
    except json.JSONDecodeError as e:
        raise ErrorGuia(f"La IA devolvió un JSON inválido: {e}")


# ─────────────────────────── revisión con código ───────────────────────────

def arreglar_ruta(valor, sub, reales, avisos):
    """Pone la carpeta si falta y corrige mayúsculas/minúsculas del nombre."""
    if not valor:
        return valor
    nombre = valor.split("/", 1)[1] if valor.startswith(sub + "/") else os.path.basename(valor)
    if nombre in reales:
        return f"{sub}/{nombre}"
    por_minusculas = {r.lower(): r for r in reales}
    if nombre.lower() in por_minusculas:
        real = por_minusculas[nombre.lower()]
        avisos.append(f"Corregí {nombre} → {real}")
        return f"{sub}/{real}"
    return f"{sub}/{nombre}"


def tamano_maximo(texto, posicion):
    ancho = W * 0.45 if posicion in ("izquierda", "derecha") else W * 0.85
    palabra = max((len(p) for p in str(texto).split()), default=1)
    return int(ancho / (0.65 * max(palabra, 1)))


def normalizar(g, nombre, d):
    avisos, errores = [], []
    reales = {sub: listar(d, sub) for sub in ("imagenes", "voz", "musica")}

    g["proyecto"] = nombre
    g["formato"] = {"ancho": 1080, "alto": 1920, "fps": 30}
    g["fuentes"] = dict(FUENTES)
    g.setdefault("voz_retraso", 0.3)
    g.setdefault("pausa_entre_escenas", 0.3)
    g["duracion_max"] = max(g.get("duracion_max", 90), 90)

    m = g.get("musica") or {}
    m["archivo"] = arreglar_ruta(m.get("archivo"), "musica", reales["musica"], avisos)
    if (not m["archivo"] or os.path.basename(m["archivo"]) not in reales["musica"]) and len(reales["musica"]) == 1:
        m["archivo"] = f"musica/{reales['musica'][0]}"
    m.setdefault("fade_out", 2)
    m.setdefault("volumen", 0.6)
    g["musica"] = m

    escenas = g.get("escenas") or []
    if not escenas:
        raise ErrorGuia("La IA no generó escenas.")

    for i, e in enumerate(escenas):
        e["id"] = str(e.get("id", i + 1))
        e["imagenes"] = [arreglar_ruta(x, "imagenes", reales["imagenes"], avisos) for x in (e.get("imagenes") or [])]
        if e.get("voz"):
            e["voz"] = arreglar_ruta(e["voz"], "voz", reales["voz"], avisos)
        elif not e.get("duracion"):
            e["duracion"] = 2

        if not e["imagenes"]:
            e["fondo"] = "negro"
            e["efecto"] = "ninguno"
        elif e.get("efecto") not in EFECTOS:
            e["efecto"] = "zoom_in_lento"

        # Montaje: convertir el texto de cada tramo en puntos de corte (proporción de caracteres)
        seg = e.pop("segmentos_texto", None)
        if seg and len(e["imagenes"]) > 1:
            if len(seg) != len(e["imagenes"]):
                avisos.append(f"Escena {e['id']}: {len(seg)} tramos de texto para {len(e['imagenes'])} imágenes")
            largos = [len(str(s)) for s in seg[:len(e["imagenes"])]]
            total, acumulado, cortes = sum(largos) or 1, 0, []
            for largo in largos[:-1]:
                acumulado += largo
                cortes.append(round(acumulado / total, 3))
            e["cortes_voz"] = cortes
            e.pop("reparto_imagenes", None)
        if len(e["imagenes"]) > 1 and not e.get("cortes_voz") and len(e["imagenes"]) > 2:
            n = len(e["imagenes"])
            e["cortes_voz"] = [round(k / n, 3) for k in range(1, n)]
            avisos.append(f"Escena {e['id']}: cortes repartidos en partes iguales")

        try:
            e["musica_vol"] = min(max(float(e.get("musica_vol", 0.15)), 0.0), 1.0)
        except (TypeError, ValueError):
            e["musica_vol"] = 0.15

        tr = e.get("transicion_salida")
        if i == len(escenas) - 1:
            e["transicion_salida"] = None
        elif not isinstance(tr, dict) or tr.get("tipo") not in TRANSICIONES:
            e["transicion_salida"] = {"tipo": "corte"}
        elif tr["tipo"] != "corte":
            tr.setdefault("duracion", 0.1 if tr["tipo"] == "fadewhite" else 0.5)

        for t in e.get("textos") or []:
            if t.get("fuente") not in FUENTES:
                t["fuente"] = "bold"
            if t.get("posicion") not in POSICIONES:
                t["posicion"] = "centro"
            if t.get("animacion") not in ANIMACIONES:
                t["animacion"] = "golpe"
            t.setdefault("color", "white")
            if "inicio" not in t and "inicio_desde_final" not in t and "segmento" not in t:
                t["inicio"] = 0
            maximo = tamano_maximo(t.get("contenido", ""), t["posicion"])
            try:
                tam = int(t.get("tamano", 80))
            except (TypeError, ValueError):
                tam = 80
            if tam > maximo:
                avisos.append(f"Escena {e['id']}: achiqué \"{t.get('contenido', '')[:25]}\" de {tam} a {maximo} para que quepa")
                tam = maximo
            t["tamano"] = tam
        e["textos"] = e.get("textos") or []

    # Archivos que no existen
    rutas = [g["musica"].get("archivo")]
    for e in escenas:
        rutas += e["imagenes"]
        if e.get("voz"):
            rutas.append(e["voz"])
    for r in rutas:
        if not r or not os.path.isfile(os.path.join(d, r)):
            errores.append(f"No existe: {r}")

    return g, avisos, errores


def duracion_audio(ruta):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                        "-of", "csv=p=0", ruta], capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def estimar_duracion(g, d):
    total = 0.0
    for e in g["escenas"]:
        if e.get("duracion"):
            total += float(e["duracion"])
        elif e.get("voz"):
            total += g["voz_retraso"] + duracion_audio(os.path.join(d, e["voz"])) + g["pausa_entre_escenas"]
    return round(total, 1)


# ─────────────────────────── todo junto ───────────────────────────

def generar(nombre, d, plantilla, proyectos, key, modelo):
    prompt = armar_prompt(nombre, d, plantilla, proyectos)
    respuesta = llamar_gemini(prompt, key, modelo)

    # Se guarda la respuesta cruda para poder revisarla si algo sale raro
    try:
        open(os.path.join(d, "guia_ia_respuesta.txt"), "w", encoding="utf-8").write(respuesta)
    except PermissionError:
        raise ErrorGuia("No tengo permiso de escribir en la carpeta del proyecto. "
                        "Corre: sudo chown -R 1000:1000 /DATA/video-editor")

    g, avisos, errores = normalizar(extraer_json(respuesta), nombre, d)
    texto = json.dumps(g, ensure_ascii=False, indent=2)

    if errores:
        open(os.path.join(d, "guia_borrador.json"), "w", encoding="utf-8").write(texto)
        raise ErrorGuia("La guía generada menciona archivos que no existen. "
                        "La guardé como guia_borrador.json.", errores)

    actual = os.path.join(d, "guia.json")
    if os.path.isfile(actual):
        os.replace(actual, os.path.join(d, "guia_anterior.json"))
    open(actual, "w", encoding="utf-8").write(texto)

    return {
        "proyecto": nombre,
        "escenas": len(g["escenas"]),
        "duracion_estimada": estimar_duracion(g, d),
        "musica": os.path.basename(g["musica"]["archivo"]),
        "avisos": avisos,
    }
