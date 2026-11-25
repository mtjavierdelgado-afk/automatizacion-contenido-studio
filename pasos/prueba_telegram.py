"""Prueba de pasos/avisos_telegram.py con un Telegram FALSO (en local).

Sin red de verdad y sin bot de verdad: un servidor HTTP en 127.0.0.1 que
contesta como la API de bots (getMe, getUpdates, sendMessage,
editMessageText). El token y el chat van a una carpeta de secretos temporal.

    python pasos/prueba_telegram.py
"""
import http.server
import json
import os
import shutil
import sys
import tempfile
import threading

AQUI = os.path.dirname(os.path.abspath(__file__))
if AQUI not in sys.path:
    sys.path.insert(0, AQUI)

_ok = 0
_fallos = []
TOKEN = "123456789:AAHabcdefghijklmnopqrstuvwxyz012345"


def ok(condicion, mensaje):
    global _ok
    if condicion:
        _ok += 1
        return True
    _fallos.append(mensaje)
    print(f"      FALLO: {mensaje}")
    return False


class Falso(http.server.BaseHTTPRequestHandler):
    recibidos = []
    caido = False

    def log_message(self, *a):
        pass

    def do_POST(self):
        largo = int(self.headers.get("Content-Length") or 0)
        cuerpo = json.loads(self.rfile.read(largo) or b"{}")
        partes = self.path.strip("/").split("/")
        token, metodo = partes[0][3:], partes[1]
        Falso.recibidos.append((metodo, cuerpo))
        if Falso.caido:
            self.send_response(502)
            self.end_headers()
            return
        if token != TOKEN:
            self._json(401, {"ok": False, "description": "Unauthorized"})
            return
        if metodo == "getMe":
            self._json(200, {"ok": True, "result": {"username": "MiStudioBot"}})
        elif metodo == "getUpdates":
            self._json(200, {"ok": True, "result": [
                {"message": {"chat": {"id": 111, "type": "private", "first_name": "Otro"}}},
                {"message": {"chat": {"id": 222, "type": "private", "first_name": "Javier",
                                      "username": "javi"}}},
                {"message": {"chat": {"id": -5, "type": "group", "title": "Grupo"}}},
            ]})
        elif metodo == "sendMessage":
            self._json(200, {"ok": True, "result": {"message_id": 77}})
        elif metodo == "editMessageText":
            self._json(200, {"ok": True, "result": True})
        else:
            self._json(404, {"ok": False, "description": "no"})

    def _json(self, codigo, datos):
        crudo = json.dumps(datos).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(crudo)))
        self.end_headers()
        self.wfile.write(crudo)


def main():
    secretos = tempfile.mkdtemp(prefix="prueba_telegram_")
    servidor = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Falso)
    threading.Thread(target=servidor.serve_forever, daemon=True).start()
    os.environ["ESTUDIO_SECRETOS"] = secretos
    os.environ["ESTUDIO_TELEGRAM_API"] = f"http://127.0.0.1:{servidor.server_port}"
    for v in ("http_proxy", "HTTP_PROXY"):
        os.environ.pop(v, None)
    import avisos_telegram as T  # noqa: PLC0415
    try:
        print("\n  CONECTAR")
        ok(not T.estado()["conectado"], "sin nada, no está conectado")
        try:
            T.poner_token("hola")
            ok(False, "un token sin forma tenía que fallar")
        except T.ErrorTelegram as fallo:
            ok(fallo.codigo == 400 and "BotFather" in str(fallo), "un token sin forma: lo dice")
        try:
            T.poner_token("123456789:AAHzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz")
            ok(False, "un token que Telegram no conoce tenía que fallar")
        except T.ErrorTelegram as fallo:
            ok("no reconoce" in str(fallo), "uno que Telegram no conoce: «no reconoce ese token»")
        e = T.poner_token(TOKEN)
        ok(e["bot"] == "MiStudioBot" and e["token_puesto"] and not e["conectado"],
           "el token bueno se guarda y dice el nombre del bot")
        ok("token" not in e and TOKEN not in json.dumps(e), "el estado NUNCA lleva el token")
        chats = T.buscar_chats()
        ok([c["id"] for c in chats] == ["222", "111"],
           f"los chats privados, el último primero (sin grupos): {chats}")
        ok(chats[0]["nombre"] == "Javier (@javi)", "con su nombre, para confirmar que eres tú")
        try:
            T.enviar("hola")
            ok(False, "sin chat no se puede mandar")
        except T.ErrorTelegram:
            ok(True, "")
        e = T.confirmar_chat("222", "Javier (@javi)", "https://studio.test/v2/")
        ok(e["conectado"] and e["base_url"] == "https://studio.test/v2", "conectado, con la dirección")
        modo = os.stat(os.path.join(secretos, "telegram.json")).st_mode & 0o777
        ok(modo == 0o600, f"el fichero del token solo lo lee el servicio ({oct(modo)})")

        print("\n  MANDAR Y EDITAR")
        Falso.recibidos.clear()
        ok(T.enviar("aviso", silencioso=True) == "77", "manda y devuelve el id del mensaje")
        metodo, cuerpo = Falso.recibidos[-1]
        ok(metodo == "sendMessage" and cuerpo["chat_id"] == "222"
           and cuerpo["disable_notification"] is True, "al chat elegido, silencioso si se pide")
        ok(T.editar("77", "nuevo"), "editar un mensaje")
        ok(not T.editar("", "nuevo"), "sin mensaje no edita (y no falla)")

        print("\n  SI TELEGRAM FALLA")
        Falso.caido = True
        try:
            T.enviar("x")
            ok(False, "con Telegram caído tenía que fallar")
        except T.ErrorTelegram:
            ok(True, "")
        ok(T.en_pausa(), "después de un fallo, espera antes de volver a intentarlo")
        n = len(Falso.recibidos)
        try:
            T.enviar("x")
        except T.ErrorTelegram as fallo:
            ok("reintenta" in str(fallo), "en la pausa ni lo intenta")
        ok(len(Falso.recibidos) == n, "(no llamó a Telegram)")
        Falso.caido = False
        ok(T.enviar("prueba", respetar_pausa=False) == "77", "«Mandar prueba» se salta la pausa")
        ok(not T.en_pausa(), "y si sale bien, la pausa se acaba")

        print("\n  DESCONECTAR")
        ok(not T.desconectar()["conectado"], "desconectar lo borra")
        ok(not os.path.exists(os.path.join(secretos, "telegram.json")), "y el fichero ya no está")
    finally:
        servidor.shutdown()
        shutil.rmtree(secretos, ignore_errors=True)
    print(f"\n  {_ok} comprobaciones bien, {len(_fallos)} fallos")
    return 1 if _fallos else 0


if __name__ == "__main__":
    sys.exit(main())
