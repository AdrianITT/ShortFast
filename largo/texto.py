"""Texto en pantalla (filtros drawtext) para 16:9."""
import os
import textwrap


def color(c):
    return "0x" + c[1:] if c.startswith("#") else c


class GeneradorTexto:
    def __init__(self, guia, carpeta, tmp):
        self.guia, self.carpeta, self.tmp = guia, carpeta, tmp
        self.ancho, self.alto = guia.formato.ancho, guia.formato.alto
        self._n = 0

    def filtros(self, plan):
        """Lista de filtros drawtext de una escena."""
        salida = []
        voz_ini = self.guia.voz_retraso if plan.voz else 0
        voz_fin = voz_ini + plan.voz_dur
        for tx in plan.escena.textos:
            t0, t1 = self._tiempos(tx, plan, voz_fin)
            fuente = os.path.join(self.carpeta, self.guia.fuentes[tx.fuente])
            col = color(tx.color)
            lado = tx.posicion in ("izquierda", "derecha")
            lineas = self._lineas(tx.contenido, tx.tamano, self.ancho * (0.4 if lado else 0.8))
            cx, y0, alto_linea = self._posicion(tx.posicion, len(lineas), tx.tamano)
            if tx.animacion == "palabra_por_palabra":
                salida += self._palabra_por_palabra(lineas, tx, fuente, col, cx, y0, alto_linea, t0, t1, plan.voz_dur)
            else:
                alpha = (f"if(lt(t,{t0:.3f}),0,min(1,(t-{t0:.3f})/0.5))" if tx.animacion == "fade" else "1")
                # golpe: el texto entra 18 % más grande y se asienta en 0.2 s (igual que en shorts)
                tam_expr = (f"{tx.tamano}*(1+0.18*max(0,1-(t-{t0:.3f})/0.2))" if tx.animacion == "golpe" else None)
                for i, linea in enumerate(lineas):
                    salida.append(self._drawtext(linea, fuente, tx.tamano, col, cx, y0 + i * alto_linea,
                                                 f"between(t,{t0:.3f},{t1:.3f})", alpha, tam_expr))
        return salida

    @staticmethod
    def _tiempos(tx, plan, voz_fin):
        t0 = max(0.0, voz_fin - tx.inicio_desde_final) if tx.inicio_desde_final is not None else tx.inicio
        if tx.fin_desde_final is not None:
            t1 = voz_fin - tx.fin_desde_final
        elif tx.duracion:
            t1 = t0 + tx.duracion
        else:
            t1 = plan.dur
        return t0, t1

    @staticmethod
    def _lineas(texto, tam, ancho):
        max_chars = max(4, int(ancho / (tam * 0.65)))
        return textwrap.wrap(texto, max_chars) or [texto]

    def _posicion(self, pos, n_lineas, tam):
        alto_linea = tam * 1.25
        cx = {"izquierda": self.ancho / 4, "derecha": 3 * self.ancho / 4}.get(pos, self.ancho / 2)
        y0 = {"arriba": self.alto * 0.12, "abajo": self.alto * 0.72,
              "abajo_firma": self.alto * 0.86}.get(pos, (self.alto - n_lineas * alto_linea) / 2)
        return cx, y0, alto_linea

    def _palabra_por_palabra(self, lineas, tx, fuente, col, cx, y0, alto_linea, t0, t1, voz_dur):
        salida = []
        total = sum(len(l.split()) for l in lineas)
        paso = min(0.35, max(0.15, voz_dur / max(1, total)))
        for k in range(1, total + 1):
            a = t0 + (k - 1) * paso
            b = t0 + k * paso if k < total else t1
            resto = k
            for i, linea in enumerate(lineas):
                palabras = linea.split()[:resto]
                resto -= len(palabras)
                if palabras:
                    salida.append(self._drawtext(" ".join(palabras), fuente, tx.tamano, col, cx,
                                                 y0 + i * alto_linea, f"between(t,{a:.3f},{b:.3f})", "1"))
                if resto <= 0:
                    break
        return salida

    def _drawtext(self, txt, fuente, tam, col, cx, y, enable, alpha, tam_expr=None):
        # El texto va en un archivo para no pelear con el escape de : , ' en FFmpeg
        self._n += 1
        archivo = os.path.join(self.tmp, f"txt_{self._n:04d}.txt")
        with open(archivo, "w", encoding="utf-8") as f:
            f.write(txt)
        borde = max(2, tam // 22)
        return (f"drawtext=fontfile='{fuente}':textfile='{archivo}':expansion=none:"
                f"fontsize='{tam_expr or tam}':fontcolor={col}:borderw={borde}:bordercolor=black@0.6:"
                f"x={cx:.1f}-text_w/2:y={y:.1f}:enable='{enable}':alpha='{alpha}'")
