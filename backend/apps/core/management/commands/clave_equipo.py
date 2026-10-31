from getpass import getpass

from django.core.management.base import BaseCommand, CommandError

from apps.core.acceso import fijar_clave


class Command(BaseCommand):
    help = "Define la clave general del equipo (el primer paso de la entrada)."

    def add_arguments(self, parser):
        parser.add_argument('clave', nargs='?', help="Si no la pasas, la pide sin mostrarla.")

    def handle(self, *args, **opciones):
        clave = opciones['clave'] or getpass("Clave general del equipo: ")
        if len(clave) < 8:
            raise CommandError("La clave necesita al menos 8 caracteres.")
        fijar_clave(clave)
        self.stdout.write(self.style.SUCCESS("Clave general del equipo guardada."))
