#!/usr/bin/env python3
"""
Render completo de un Short a partir de su guia.json

Uso (desde el servidor):
    docker exec ffmpeg-api python /app/render.py short_09_soledad

Lee:    /data/proyectos/<nombre>/guia.json
Genera: /data/salida/<nombre>.mp4
Temp:   /data/salida/tmp_<nombre>/   (clips por escena, útil para depurar)
"""
import json
import os
import subprocess
import sys
import textwrap
import time

W, H, FPS = 1080, 1920, 30
FRAME = 1 / FPS
PROYECTOS = os.environ.get("PROYECTOS", "/data/proyectos")
SALIDA = os.environ.get("SALIDA", "/data/salida")

# Nombre en la guía -> transición de xfade
XFADE = {
    "corte": "fade",        # un "fade" de 1 frame = corte duro
    "fade": "fade",
    "fadeblack": "fadeblack",
    "fadewhite": "fadewhite",  # flash blanco
    "dissolve": "dissolve",
}

ENC_CLIP = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", str(FPS)]

BASE_IMG = "scale=1620:2880:force_original_aspect_ratio=increase,crop=1620:2880"


# ─────────────────────────── utilidades ───────────────────────────

def log(msg):
    print(msg, flush=True)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        log(r.stderr[-4000:])
        raise SystemExit(f"❌ Falló el comando: {' '.join(cmd[:8])} ...")
    return r


def duracion(ruta):
    r = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "csv=p=0", ruta])
    return float(r.stdout.strip())


def frames(seg):
    return max(1, round(seg * FPS))


def color(c):
    return "0x" + c[1:] if c.startswith("#") else c


def trans_dur(tr):
    if not tr:
        return 0
    if tr["tipo"] == "corte":
        return FRAME
    return tr.get("duracion", 0.5)


# ─────────────────────────── efectos ───────────────────────────

def zoompan(efecto, n):
    cx, cy = "iw/2-(iw/zoom/2)", "ih/2-(ih/zoom/2)"
    if efecto == "zoom_in_lento":
        z, x, y = f"1+0.08*on/{n}", cx, cy
    elif efecto == "zoom_in":
        z, x, y = f"1+0.15*on/{n}", cx, cy
    elif efecto == "zoom_out":
        z, x, y = f"1.15-0.15*on/{n}", cx, cy
    elif efecto == "paneo_der":
        z, x, y = "1.15", f"(iw-iw/zoom)*on/{n}", cy
    elif efecto == "paneo_rapido":
        z, x, y = "1.25", f"(iw-iw/zoom)*on/{n}", cy
    else:  # ninguno
        z, x, y = "1", "0", "0"
    return f"zoompan=z='{z}':x='{x}':y='{y}':d={n}:s={W}x{H}:fps={FPS}"


# ─────────────────────────── texto ───────────────────────────

_contador_txt = [0]


def lineas(texto, tam, ancho):
    max_chars = max(4, int(ancho / (tam * 0.65)))
    return textwrap.wrap(texto, max_chars) or [texto]


def posicion(pos, n_lineas, tam):
    lh = tam * 1.25
    cx = {"izquierda": W / 4, "derecha": 3 * W / 4}.get(pos, W / 2)
    if pos == "arriba":
        y0 = H * 0.15
    elif pos == "abajo":
        y0 = H * 0.70
    elif pos == "abajo_firma":
        y0 = H * 0.84
    else:  # centro, izquierda, derecha
        y0 = (H - n_lineas * lh) / 2
    return cx, y0, lh


def drawtext(txt, fuente, tam, col, cx, y, enable, alpha, tmp):
    # El texto va en un archivo para no pelear con el escape de : , ' en FFmpeg
    _contador_txt[0] += 1
    f = os.path.join(tmp, f"txt_{_contador_txt[0]:03d}.txt")
    with open(f, "w", encoding="utf-8") as fh:
        fh.write(txt)
    borde = max(2, tam // 22)
    return (f"drawtext=fontfile='{fuente}':textfile='{f}':expansion=none:"
            f"fontsize={tam}:fontcolor={col}:borderw={borde}:bordercolor=black@0.6:"
            f"x={cx:.1f}-text_w/2:y={y:.1f}:enable='{enable}':alpha='{alpha}'")


def filtros_texto(p, guia, proj, tmp):
    esc, dur = p["esc"], p["dur"]
    voz_ini = guia.get("voz_retraso", 0.3) if p["voz"] else 0
    out = []
    for tx in esc.get("textos", []):
        voz_fin = voz_ini + p["voz_dur"]
        if "segmento" in tx:  # texto ligado a un tramo de una escena con varias imágenes
            k, cortes = tx["segmento"], p.get("cortes", [])
            fin_voz_seg = cortes[k] if k < len(cortes) else voz_fin
            t0 = max(0.0, fin_voz_seg - tx.get("adelanto", 0.8))
            t1 = cortes[k] if k < len(cortes) else dur
        else:
            if "inicio_desde_final" in tx:
                t0 = max(0.0, voz_fin - tx["inicio_desde_final"])
            else:
                t0 = tx.get("inicio", 0)
            if "fin_desde_final" in tx:
                t1 = voz_fin - tx["fin_desde_final"]
            elif tx.get("duracion"):
                t1 = t0 + tx["duracion"]
            else:
                t1 = dur

        fuente = os.path.join(proj, guia["fuentes"][tx.get("fuente", "bold")])
        tam = tx.get("tamano", 80)
        col = color(tx.get("color", "white"))
        pos = tx.get("posicion", "centro")
        ancho = W * 0.45 if pos in ("izquierda", "derecha") else W * 0.85
        anim = tx.get("animacion", "ninguna")

        full = lineas(tx["contenido"], tam, ancho)
        cx, y0, lh = posicion(pos, len(full), tam)

        if anim == "palabra_por_palabra":
            total = sum(len(l.split()) for l in full)
            paso = min(0.35, max(0.15, p["voz_dur"] / max(1, total)))
            for k in range(1, total + 1):
                a = t0 + (k - 1) * paso
                b = t0 + k * paso if k < total else t1
                resto = k
                for li, linea in enumerate(full):
                    ws = linea.split()[:resto]
                    resto -= len(ws)
                    if ws:
                        out.append(drawtext(" ".join(ws), fuente, tam, col, cx,
                                            y0 + li * lh,
                                            f"between(t,{a:.3f},{b:.3f})", "1", tmp))
                    if resto <= 0:
                        break
        else:
            alpha = (f"if(lt(t,{t0:.3f}),0,min(1,(t-{t0:.3f})/0.5))"
                     if anim == "fade" else "1")
            for li, linea in enumerate(full):
                out.append(drawtext(linea, fuente, tam, col, cx, y0 + li * lh,
                                    f"between(t,{t0:.3f},{t1:.3f})", alpha, tmp))
    return out


# ─────────────────────────── escenas ───────────────────────────

def render_escena(p, guia, proj, tmp, idx):
    esc, n = p["esc"], p["n"]
    salida = os.path.join(tmp, f"escena_{idx:02d}.mp4")
    textos = filtros_texto(p, guia, proj, tmp)
    imgs = [os.path.join(proj, i) for i in (esc.get("imagenes") or [])]
    efecto = esc.get("efecto", "ninguno")
    cola_txt = ("," + ",".join(textos)) if textos else ""

    if not imgs:  # fondo negro + texto
        cmd = ["ffmpeg", "-y", "-f", "lavfi",
               "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={n / FPS:.4f}",
               "-vf", "format=yuv420p,setsar=1" + cola_txt,
               "-frames:v", str(n)] + ENC_CLIP + [salida]

    elif esc.get("encuadre") == "ajustar":  # logo: completo, centrado, sobre negro
        fc = (f"[1:v]scale={int(W * 0.8)}:{int(H * 0.6)}:force_original_aspect_ratio=decrease[l];"
              f"[0:v][l]overlay=(W-w)/2:(H-h)/2-150,format=yuv420p,setsar=1{cola_txt}[v]")
        cmd = ["ffmpeg", "-y", "-f", "lavfi",
               "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={n / FPS:.4f}",
               "-i", imgs[0], "-filter_complex", fc, "-map", "[v]",
               "-frames:v", str(n)] + ENC_CLIP + [salida]

    elif len(imgs) > 1 and p.get("cortes"):  # varias imágenes, corte duro en cada tramo
        limites = [0] + [frames(c) for c in p["cortes"]] + [n]
        fc, etiquetas = [], ""
        for k in range(len(imgs)):
            nk = limites[k + 1] - limites[k]
            fc.append(f"[{k}:v]{BASE_IMG},{zoompan(efecto, nk)},setsar=1,"
                      f"format=yuv420p[s{k}]")
            etiquetas += f"[s{k}]"
        fc.append(f"{etiquetas}concat=n={len(imgs)}:v=1:a=0[x]")
        fc.append(f"[x]tpad=stop_mode=clone:stop=-1{cola_txt}[v]")
        entradas = []
        for im in imgs:
            entradas += ["-i", im]
        cmd = ["ffmpeg", "-y"] + entradas + ["-filter_complex", ";".join(fc),
               "-map", "[v]", "-frames:v", str(n)] + ENC_CLIP + [salida]

    elif len(imgs) == 1:
        vf = f"{BASE_IMG},{zoompan(efecto, n)},setsar=1,format=yuv420p" + cola_txt
        cmd = ["ffmpeg", "-y", "-i", imgs[0], "-vf", vf,
               "-frames:v", str(n)] + ENC_CLIP + [salida]

    else:  # dos imágenes con transición interna (escena 9)
        ti = (esc.get("transicion_interna") or {"tipo": "dissolve", "duracion": 1})
        n_int = frames(ti.get("duracion", 1))
        n_a = (n + n_int) // 2
        n_b = n + n_int - n_a
        tipo = XFADE.get(ti.get("tipo", "dissolve"), "dissolve")
        fc = [
            f"[0:v]{BASE_IMG},{zoompan(efecto, n_a)},setsar=1,format=yuv420p,settb=AVTB,fps={FPS}[a]",
            f"[1:v]{BASE_IMG},{zoompan(efecto, n_b)},setsar=1,format=yuv420p,settb=AVTB,fps={FPS}[b]",
            f"[a][b]xfade=transition={tipo}:duration={n_int / FPS:.4f}:offset={(n_a - n_int) / FPS:.4f}[x]",
            f"[x]null{cola_txt}[v]",
        ]
        cmd = ["ffmpeg", "-y", "-i", imgs[0], "-i", imgs[1],
               "-filter_complex", ";".join(fc), "-map", "[v]",
               "-frames:v", str(n)] + ENC_CLIP + [salida]

    run(cmd)
    return salida


def unir(plan, clips, tmp):
    cmd = ["ffmpeg", "-y"]
    for c in clips:
        cmd += ["-i", c]
    fc = [f"[{i}:v]settb=AVTB,fps={FPS},format=yuv420p,setsar=1[v{i}]"
          for i in range(len(clips))]
    reales = [duracion(c) for c in clips]  # por si algún clip salió con un frame de menos
    acc, acc_len = "v0", reales[0]
    for i in range(1, len(clips)):
        prev = plan[i - 1]
        tipo = XFADE.get(prev["esc"]["transicion_salida"]["tipo"], "fade")
        td = prev["td"]
        fc.append(f"[{acc}][v{i}]xfade=transition={tipo}:duration={td:.4f}"
                  f":offset={acc_len - td:.4f}[x{i}]")
        acc = f"x{i}"
        acc_len += reales[i] - td
    salida = os.path.join(tmp, "video.mp4")
    cmd += ["-filter_complex", ";".join(fc), "-map", f"[{acc}]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", salida]
    run(cmd)
    return salida


# ─────────────────────────── audio ───────────────────────────

def expr_volumen(inicios, vols, rampa=0.5):
    def val(k):
        if k == 0:
            return f"{vols[0]}"
        d = vols[k] - vols[k - 1]
        return f"{vols[k - 1]}+({d:.3f})*min(1,(t-{inicios[k]:.3f})/{rampa})"
    e = val(len(vols) - 1)
    for k in range(len(vols) - 2, -1, -1):
        e = f"if(lt(t,{inicios[k + 1]:.3f}),{val(k)},{e})"
    return e


def mezclar_audio(plan, guia, proj, total, tmp):
    ret = guia.get("voz_retraso", 0.3)
    voces = [(os.path.join(proj, p["esc"]["voz"]), p["inicio"] + ret)
             for p in plan if p["voz"]]
    musica = os.path.join(proj, guia["musica"]["archivo"])
    fade_out = guia["musica"].get("fade_out", 2)
    factor = guia["musica"].get("volumen", 1.0)  # control general: 1.0 = tal cual
    vols = [round(p["esc"].get("musica_vol", 0.15) * factor, 4) for p in plan]
    inicios = [p["inicio"] for p in plan]

    cmd = ["ffmpeg", "-y"]
    for v, _ in voces:
        cmd += ["-i", v]
    cmd += ["-stream_loop", "-1", "-i", musica]

    fmt = "aformat=sample_rates=48000:channel_layouts=stereo"
    fc, labels = [], ""
    for i, (_, ini) in enumerate(voces):
        ms = int(ini * 1000)
        fc.append(f"[{i}:a]{fmt},adelay={ms}:all=1[a{i}]")
        labels += f"[a{i}]"
    fc.append(f"{labels}amix=inputs={len(voces)}:normalize=0:duration=longest[voz]")
    m = len(voces)
    fc.append(f"[{m}:a]{fmt},atrim=0:{total:.3f},asetpts=PTS-STARTPTS,"
              f"volume='{expr_volumen(inicios, vols)}':eval=frame,"
              f"afade=t=out:st={max(0, total - fade_out):.3f}:d={fade_out}[mus]")
    fc.append(f"[voz][mus]amix=inputs=2:normalize=0:duration=longest,"
              f"atrim=0:{total:.3f},alimiter=limit=0.95[out]")

    salida = os.path.join(tmp, "audio.wav")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[out]",
            "-t", f"{total:.3f}", "-c:a", "pcm_s16le", salida]
    run(cmd)
    return salida


# ─────────────────────────── main ───────────────────────────

def main():
    if len(sys.argv) < 2:
        raise SystemExit("Uso: python render.py <nombre_proyecto>")
    nombre = sys.argv[1]
    proj = os.path.join(PROYECTOS, nombre)
    guia = json.load(open(os.path.join(proj, "guia.json"), encoding="utf-8"))
    tmp = os.path.join(SALIDA, f"tmp_{nombre}")
    os.makedirs(tmp, exist_ok=True)
    t_ini = time.time()

    ret = guia.get("voz_retraso", 0.3)
    pausa = guia.get("pausa_entre_escenas", 0.3)

    # 1. Plan: duración de cada escena según su voz
    log("📏 Midiendo audios...")
    plan = []
    for e in guia["escenas"]:
        voz = os.path.join(proj, e["voz"]) if e.get("voz") else None
        vd = duracion(voz) if voz else 0
        td = trans_dur(e.get("transicion_salida"))
        base = e["duracion"] if e.get("duracion") else ret + vd + pausa
        n = frames(base + td)  # se suma la transición para que no se coma contenido
        cortes = [ret + vd * f for f in e.get("cortes_voz", [])]
        plan.append(dict(esc=e, voz=voz, voz_dur=vd, td=td, n=n, dur=n / FPS, cortes=cortes))

    t = 0.0
    for p in plan:
        p["inicio"] = t
        t += p["dur"] - p["td"]
    total = t

    log(f"\n{'Esc':>4} {'Inicia':>8} {'Dura':>6}")
    for p in plan:
        log(f"{p['esc']['id']:>4} {p['inicio']:>7.1f}s {p['dur']:>5.1f}s")
    log(f"TOTAL: {total:.1f}s")
    if total > guia.get("duracion_max", 999):
        log(f"⚠️  Pasa de duracion_max ({guia['duracion_max']}s)")

    # 2. Clips por escena
    clips = []
    for i, p in enumerate(plan, 1):
        log(f"🎬 Escena {i}/{len(plan)} ({p['dur']:.1f}s)...")
        clips.append(render_escena(p, guia, proj, tmp, i))

    # 3. Unir con transiciones
    log("🔗 Uniendo escenas con transiciones...")
    video = unir(plan, clips, tmp)

    # 4. Audio: voces en su lugar + música con volumen por escena
    log("🎵 Mezclando voz y música...")
    audio = mezclar_audio(plan, guia, proj, total, tmp)

    # 5. Exportar
    final = os.path.join(SALIDA, f"{nombre}.mp4")
    log("📦 Exportando...")
    run(["ffmpeg", "-y", "-i", video, "-i", audio, "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-shortest",
         "-movflags", "+faststart", final])

    log(f"\n✅ Listo: {final}")
    log(f"   Duración: {duracion(final):.1f}s | Tardó: {(time.time() - t_ini) / 60:.1f} min")


if __name__ == "__main__":
    main()
