from ..cliente_api import ErrorApi
from ..tts import ErrorTts
from ..voces import ErrorGuionVoces, GuionVoces
from .base import Interfaz

ICONOS = {"ok": "✅", "renderizando": "⏳", "error": "❌", "sin_render": "⚪"}


class InterfazTerminal(Interfaz):
    nombre = "terminal"

    def iniciar(self):
        print("\n=== ffmpeg-api · panel ===")
        while True:
            try:
                if not self._menu_principal():
                    return
            except (ErrorApi, ErrorTts, ErrorGuionVoces) as e:
                print(f"\n❌ {e}")
            except (KeyboardInterrupt, EOFError):
                print()
                return

    def _menu_principal(self):
        opciones = ["Elegir un proyecto", "Crear proyecto nuevo", "Indexar música de proyectos anteriores"]
        opcion = self._elegir("Menú principal", opciones, "Salir")
        if opcion == 0:
            return False
        if opcion == 1:
            self._menu_proyectos()
        elif opcion == 2:
            self._crear()
        else:
            self._indexar_biblioteca()
        return True

    def _indexar_biblioteca(self):
        resultados = self.servicio.indexar_biblioteca()
        if not resultados:
            print("Ningún proyecto tiene música referenciada en su guia.json.")
            return
        for proyecto, pista, estado in resultados:
            print(f"  {proyecto}" + (f" · {pista}" if pista else "") + f" — {estado}")

    def _menu_proyectos(self):
        proyectos = self.servicio.listar()
        if not proyectos:
            print("No hay proyectos todavía.")
            return
        etiquetas = [f"{ICONOS.get(p['estado'], '?')} {'📄' if p['tiene_guia'] else '  '} {p['proyecto']}"
                     for p in proyectos]
        opcion = self._elegir("Proyectos (✅ listo · ⏳ renderizando · ❌ error · 📄 con guía)", etiquetas, "Volver")
        if opcion:
            self._menu_acciones(proyectos[opcion - 1]["proyecto"])

    def _menu_acciones(self, nombre):
        acciones = [
            ("Revisar qué hay subido", self._revisar),
            ("Generar voces (pegar guion)", self._voces),
            ("Generar guía con IA (Gemini)", self._guia_ia),
            ("Generar guía desde borrador (local)", self._guia_local),
            ("Renderizar", self._renderizar),
            ("Ver estado del render", self._estado),
            ("Descargar video", self._descargar),
        ]
        while True:
            opcion = self._elegir(f"Proyecto: {nombre}", [a[0] for a in acciones], "Volver")
            if not opcion:
                return
            try:
                acciones[opcion - 1][1](nombre)
            except (ErrorApi, ErrorTts, ErrorGuionVoces) as e:
                print(f"\n❌ {e}")

    # ───────── acciones ─────────

    def _crear(self):
        nombre = input("Nombre del proyecto (letras, números, _ y -; vacío cancela): ").strip()
        if nombre:
            carpeta = self.servicio.crear(nombre)
            print(f"✅ Creado. Sube los archivos a: {carpeta}")

    def _revisar(self, nombre):
        r = self.servicio.revisar(nombre)
        print(f"Imágenes: {r['imagenes']} · Voces: {r['voces']} · Música: {r['musica']} · "
              f"Guía: {'sí' if r['tiene_guia'] else 'no'}")
        for f in r["faltan"]:
            print(f"  ⚠ falta {f}")
        if r["tiene_guia"] and not r["faltan"]:
            print("✅ Listo para renderizar")

    def _voces(self, nombre):
        voces = self.servicio.voces
        print("Pega tu guion (script bash o líneas «archivo.mp3 | texto»).")
        print("Cuando termines, escribe FIN en una línea sola (FIN al inicio cancela).")
        texto = self._pegar_hasta_fin()
        try:
            if not texto.strip():
                print("Cancelado.")
                return
            guion = voces.preparar(texto)
            if not guion.voz:  # sin voz en el guion: ofrece elegir (Enter = la de siempre)
                guion.voz = self._elegir_voz(voces)
            self._generar_voces(nombre, guion, self._elegir_velocidad(voces))
        finally:
            texto = guion = None  # el guion pegado no se conserva

    @staticmethod
    def _elegir_voz(voces):
        """Lista numerada de voces; Enter, un id o un número. Devuelve None para la de por defecto."""
        ids = []
        for titulo, grupo in voces.voces_disponibles():
            print(f"\n{titulo}:")
            for i in grupo:
                ids.append(i)
                print(f"  {len(ids):>2}) {i}")
        eleccion = input(f"\nVoz (número o nombre; Enter = {voces.voz_por_defecto}): ").strip()
        if eleccion.isdigit() and 1 <= int(eleccion) <= len(ids):
            return ids[int(eleccion) - 1]
        return eleccion if eleccion in ids else None

    @staticmethod
    def _elegir_velocidad(voces):
        """Pide la velocidad (Enter = la de por defecto); repite si no es válida."""
        while True:
            texto = input(f"Velocidad (0.5-1.5; Enter = {voces.velocidad_por_defecto}): ")
            try:
                return voces.velocidad_valida(texto)
            except ErrorGuionVoces as e:
                print(f"⚠ {e}")

    def _generar_voces(self, nombre, guion, velocidad=None):
        voces = self.servicio.voces
        print(f"\nVoz: {guion.voz or voces.voz_por_defecto} · Velocidad: {velocidad or voces.velocidad_por_defecto} · {len(guion.tramos)} tramos")
        for t in guion.tramos:
            print(f"  • {t.archivo} ({len(t.texto)} caracteres)")
        existentes = voces.existentes(nombre, guion)
        sobrescribir = False
        if existentes:
            print(f"Ya existen {len(existentes)} de {len(guion.tramos)} audios.")
            sobrescribir = self._confirmar("¿Sobrescribirlos? (No = solo generar los que faltan)")
        if not self._confirmar("¿Generar ahora?", por_defecto=True):
            print("Cancelado.")
            return
        while True:
            fallidos, generados = [], 0
            for r in voces.generar(nombre, guion, sobrescribir, velocidad):
                if r.estado == "error":
                    fallidos.append(r.archivo)
                    print(f"  ❌ {r.archivo}: {r.detalle}")
                else:
                    generados += r.estado == "generado"
                    print(f"  {'✅' if r.estado == 'generado' else '⏭ '} {r.archivo}" + (" (ya existía)" if r.estado == "omitido" else ""))
            if not fallidos:
                if generados:
                    print(f"\n✅ Éxito: {generados} {'voz generada' if generados == 1 else 'voces generadas'} en {nombre}/voz/")
                else:
                    print("\nNada que generar: todos los audios ya existían.")
                return
            print(f"\n⚠ Fallaron {len(fallidos)} de {len(guion.tramos)}.")
            if not self._confirmar("¿Reintentar los fallidos?", por_defecto=True):
                return
            guion = GuionVoces(guion.voz, [t for t in guion.tramos if t.archivo in fallidos])
            sobrescribir = True

    def _guia_ia(self, nombre):
        print("Generando guía con Gemini (puede tardar)...")
        self.servicio.generar_guia_ia(nombre)
        print("✅ Guía generada")

    def _guia_local(self, nombre):
        r = self.servicio.generar_guia_local(nombre)
        print("✅ Guía generada")
        for a in r["avisos"]:
            print(f"  ⚠ {a}")

    def _renderizar(self, nombre):
        self.servicio.renderizar(nombre)
        print("⏳ Render iniciado. Ctrl+C para dejar de mirar (el render sigue).")
        self._seguir(nombre)

    def _estado(self, nombre):
        e = self.servicio.estado(nombre)
        print(f"{ICONOS.get(e['estado'], '?')} {e['estado']}")
        if e["log"]:
            print(e["log"])
        if e["estado"] == "renderizando" and self._confirmar("¿Seguir el progreso?"):
            self._seguir(nombre)

    def _seguir(self, nombre):
        try:
            for e in self.servicio.seguir_render(nombre):
                ultima = e["log"].splitlines()[-1] if e["log"] else ""
                print(f"  {ICONOS.get(e['estado'], '?')} {e['estado']} · {ultima}")
        except KeyboardInterrupt:
            print("\nDejaste de mirar; el render sigue en el servidor.")
            return
        if e["estado"] == "ok":
            print("✅ Render terminado")
        else:
            print("❌ El render falló:\n" + e["log"])

    def _descargar(self, nombre):
        print("Descargando...")
        print(f"✅ Guardado en {self.servicio.descargar_video(nombre)}")

    # ───────── utilidades de entrada ─────────

    @staticmethod
    def _elegir(titulo, opciones, texto_salida):
        """Muestra un menú numerado. Devuelve 0 para salir o el número elegido (base 1)."""
        while True:
            print(f"\n{titulo}")
            for i, o in enumerate(opciones, 1):
                print(f"  {i}) {o}")
            print(f"  0) {texto_salida}")
            texto = input("> ").strip()
            if texto.isdigit() and 0 <= int(texto) <= len(opciones):
                return int(texto)
            print("Opción no válida.")

    @staticmethod
    def _pegar_hasta_fin():
        lineas = []
        try:
            while (linea := input()).strip().upper() != "FIN":
                lineas.append(linea)
        except EOFError:
            pass
        return "\n".join(lineas)

    @staticmethod
    def _confirmar(pregunta, por_defecto=False):
        respuesta = input(f"{pregunta} [{'S/n' if por_defecto else 's/N'}] ").strip().lower()
        return por_defecto if not respuesta else respuesta in ("s", "si", "sí")
