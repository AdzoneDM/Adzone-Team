"""Genera las claves VAPID para las notificaciones en el celular. Se pegan en backend/.env (una sola vez)."""
import base64

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Genera VAPID_PUBLICA y VAPID_PRIVADA para backend/.env'

    def handle(self, *args, **options):
        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec
        clave = ec.generate_private_key(ec.SECP256R1())
        privada = base64.urlsafe_b64encode(clave.private_numbers().private_value.to_bytes(32, 'big')).decode().rstrip('=')
        publica = base64.urlsafe_b64encode(clave.public_key().public_bytes(
            serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)).decode().rstrip('=')
        self.stdout.write('Pega estas líneas en backend/.env y reinicia la app (no las compartas):\n')
        self.stdout.write(f'VAPID_PUBLICA={publica}')
        self.stdout.write(f'VAPID_PRIVADA={privada}')
        self.stdout.write('VAPID_CORREO=adzonedigitalm@gmail.com')
