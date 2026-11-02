import argparse
import json
from decimal import Decimal, InvalidOperation
import xml.etree.ElementTree as ET

DESTINO = "/queue/pedidos"

def construir_mensaje(formato: str, pedido: dict, texto: str) -> tuple[str, str]:
    if formato == "texto":
        return texto, "text/plain; charset=utf-8"
    if formato == "fijo":
        # Contrato Fixed 36 chars: ID[6], CLIENTE[20], MONTO[10]
        identificador = str(pedido["id"])
        cliente = str(pedido["cliente"])
        monto = Decimal(pedido["monto"])
        monto_campo = f"{monto:010.2f}"
        if not (identificador.isascii() and identificador.isdigit() and len(identificador) <= 6):
            raise ValueError("En formato fijo, --id debe tener hasta 6 digitos ASCII")
        if len(cliente) > 20 or any(ord(c) > 127 for c in cliente):
            raise ValueError("En formato fijo, --cliente admite hasta 20 caracteres ASCII")
        if monto < 0 or len(monto_campo) != 10:
            raise ValueError("En formato fijo, --monto debe estar entre 0 y 99999999.99")
        return f"{identificador.zfill(6)}{cliente:<20}{monto_campo}", "text/plain; charset=utf-8"
    if formato == "json":
        return json.dumps(pedido, ensure_ascii=False), "application/json; charset=utf-8"
    if formato == "xml":
        raiz = ET.Element("pedido")
        for clave, valor in pedido.items():
            ET.SubElement(raiz, clave).text = str(valor)
        return ET.tostring(raiz, encoding="unicode"), "application/xml; charset=utf-8"
    raise ValueError(f"Formato desconocido: {formato}")

def main():
    parser = argparse.ArgumentParser(description="Productor STOMP")
    parser.add_argument("--formato", choices=["texto", "fijo", "xml", "json"], required=True)
    parser.add_argument("--mensaje", default="Hola desde el productor STOMP")
    parser.add_argument("--id", default="123")
    parser.add_argument("--cliente", default="Ed jobs")
    parser.add_argument("--monto", default="123.45")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=61613)
    parser.add_argument("--usuario", default="demo")
    parser.add_argument("--clave", default="demo123")
    args = parser.parse_args()

    try:
        monto = Decimal(args.monto)
        if not monto.is_finite():
            raise ValueError("El monto debe ser un número finito")
    except InvalidOperation as exc:
        parser.error(f"Monto no válido: {args.monto}")
    pedido = {"id": args.id, "cliente": args.cliente, "monto": str(monto)}
    try:
        cuerpo, mime = construir_mensaje(args.formato, pedido, args.mensaje)
    except ValueError as excc:
        parser.error(str(exc))

    # Enviar mensaje al broker
    conexion = stomp.Connection12([(args.host, args.port)], vhost="/")
    try:
        conexion.connect(args.usuario, args.clave, wait=True)
        conexion.send(
            destination=DESTINO,
            body=cuerpo,
            headers={
                "content-type": mime,
                "x-formato": args.formato,
                "persistent": "true",
            },
        )
        print(f"Mensaje enviado a {DESTINO} (formato={args.formato}):\n{cuerpo}")
    finally:
        if conexion.is_connected():
            conexion.disconnect()


if __name__ == "__main__":
    main()

import argparse
import json
import time
import xml.etree.ElementTree as ET

import stomp
DESTINO = "/queue/pedidos"

def interpretar(cuerpo: str, headers: dict):
    formato = headers.get("x-formato", "").lower()
    tipo_mime = headers.get("content-type", "").lower()
    if not formato:
        if "application/json" in tipo_mime:
            formato="json"
        elif "application/xml" in tipo_mime or "text/xml" in tipo_mime:
            formato="xml"
        else:
            formato = "texto"
    if formato == "texto":
        return formato, cuerpo
    if formato == "fijo":
        if len(cuerpo) != 36:
            raise ValueError(f"Registro de ancho fijo inválido: {len(cuerpo)} se espera 36")
        identificador = cuerpo[0:6]
        cliente = cuerpo[6:26].rstrip()
        monto = cuerpo[26:36]
        if not (identificador.isascii() and identificador.isdigit() and len(monto) == 10 and monto[:7].isdigit() and monto[7] == "." and monto[8:].isdigit()):
            raise ValueError("Campos numericos de ancho fijo inválidos")
        return formato, {"id": identificador, "cliente": cliente, "monto": monto}
    if formato == "json":
        return formato, json.loads(cuerpo)
    if formato == "xml":
        raiz = ET.fromstring(cuerpo)
        if raiz.tag != "pedido":
            raise ValueError("El nodo raíz de XML debe ser <pedido>")    
        return formato, {elemento.tag: elemento.text for elemento in raiz}
    raise ValueError(f"Formato no soportado: {formato}")

class Escuchador(stomp.ConnectionListener):
    def __init__(self, conexion):
        self.conexion = conexion
    def on_error(self, frame):
        print(f"ERROR del broker: {frame.body}")
    def on_disconnected(self):
        print("Conexión STOMP cerrada")
    def on_message(self, frame):
        ack_id = frame.headers["ack"]
        try:
            formato, contenido = interpretar(frame.body, frame.headers)
            print(f"\n[RECIBIDO] formato={formato}")
            if isinstance(contenido, str):
                print(contenido)
            else:
                print(json.dumps(contenido, ensure_ascii=False, indent=2))
            self.conexion.ack(id=ack_id)
        except Exception as exc:
            print(f"[MENSAJE NO VÁLIDO] {exc}")
            self.conexion.nack(id=ack_id, requeue="false")

def main():
    parser = argparse.ArgumentParser(description="Consumidor STOMP")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", default=61613)
    parser.add_argument("--usuario", default="demo")
    parser.add_argument("--clave", default="demo123")
    args = parser.parse_args()
    conexion = stomp.Connection12([(args.host, args.port)], vhost="/")
    conexion.set_listener("pedidos", Escuchador(conexion))
    try: 
        conexion.connect(args.usuario, args.clave, wait=True)
        conexion.subscribe(
            destination=DESTINO, id="lector-pedidos",
            ack="client-individual", headers={"prefetch-count": "1"}
        )
        print(f"Escuchando {DESTINO}. Presiona Ctrl+C para salir.")
        while conexion.is_connected():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nDeteniendo consumidor...")
    finally:
        if conexion.is_connected():
            conexion.disconnect()

if __name__ == "__main__":
    main()
