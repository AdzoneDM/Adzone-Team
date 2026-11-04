from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import PerfilUsuario, PuestoDeTrabajo

from apps.core.permisos import PERFILES  # noqa: E402

ROLES = list(PERFILES)  # perfiles de acceso (ver apps/core/permisos.py)


PERFIL_EDITABLE = ('puesto_trabajo', 'horas_semana', 'costo_hora', 'salario_mensual', 'nomina')


def costo_desde_salario(perfil, datos):
    """Si cambian el salario y no mandan un costo por hora propio, el costo por hora se calcula del salario."""
    if 'salario_mensual' in datos and datos.get('costo_hora') in (None, ''):
        perfil.costo_hora = PerfilUsuario.costo_hora_de_salario(perfil.salario_mensual, perfil.horas_semana)


class PuestoDeTrabajoSerializer(serializers.ModelSerializer):
    departamento_nombre = serializers.CharField(source='departamento.nombre', read_only=True)
    supervisor_nombre = serializers.CharField(source='supervisor.nombre', read_only=True, default=None)
    personas = serializers.SerializerMethodField()
    subordinados = serializers.SerializerMethodField()

    class Meta:
        model = PuestoDeTrabajo
        fields = [
            'id', 'nombre',
            'departamento', 'departamento_nombre',
            'supervisor', 'supervisor_nombre',
            'funciones_principales', 'objetivo', 'perfil_ideal', 'compensacion_variable', 'beneficios',
            'alineacion_cultural', 'personas', 'subordinados',
            'fecha_creacion', 'fecha_modificacion',
        ]
        extra_kwargs = {
            'departamento': {'required': True},
            'supervisor': {'required': False, 'allow_null': True},
        }

    def get_personas(self, obj):
        return [
            {'id': p.user_id, 'nombre': p.user.get_full_name() or p.user.username}
            for p in obj.perfiles_usuarios.all() if p.user.is_active
        ]

    def get_subordinados(self, obj):
        return obj.subordinados.count()

    def validate_nombre(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Escribe el nombre del puesto.")
        return value

    def validate(self, data):
        supervisor = data.get('supervisor', getattr(self.instance, 'supervisor', None))
        if self.instance and supervisor:
            # Evita ciclos: un puesto no puede reportar a sí mismo ni a alguien que le reporta.
            actual = supervisor
            while actual is not None:
                if actual.pk == self.instance.pk:
                    raise serializers.ValidationError(
                        {"supervisor": "Ese puesto ya reporta (directa o indirectamente) a este. Se formaría un ciclo."})
                actual = actual.supervisor
        return data


class PerfilUsuarioSerializer(serializers.ModelSerializer):
    puesto_trabajo_detalle = PuestoDeTrabajoSerializer(source='puesto_trabajo', read_only=True)

    class Meta:
        model = PerfilUsuario
        fields = ['user', 'puesto_trabajo', 'puesto_trabajo_detalle', 'fecha_creacion_perfil', 'fecha_modificacion_perfil']
        extra_kwargs = {'puesto_trabajo': {'required': False, 'allow_null': True}}


class GroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = Group
        fields = ['name']


class UserSerializer(serializers.ModelSerializer):
    puesto_trabajo_id = serializers.PrimaryKeyRelatedField(
        queryset=PuestoDeTrabajo.objects.all(), source='perfil.puesto_trabajo',
        write_only=True, required=False, allow_null=True,
    )
    perfil = PerfilUsuarioSerializer(read_only=True)
    groups = GroupSerializer(many=True, read_only=True)
    roles_asignados = serializers.ListField(child=serializers.CharField(max_length=80), write_only=True, required=False)
    nombre = serializers.SerializerMethodField()
    puesto = serializers.CharField(source='perfil.puesto_trabajo.nombre', read_only=True, default=None)
    puesto_id = serializers.IntegerField(source='perfil.puesto_trabajo_id', read_only=True, default=None)
    departamento = serializers.CharField(source='perfil.puesto_trabajo.departamento.nombre', read_only=True, default=None)
    roles = serializers.SerializerMethodField()
    horas_semana = serializers.DecimalField(source='perfil.horas_semana', max_digits=4, decimal_places=1, required=False,
                                            min_value=1, max_value=80)
    costo_hora = serializers.DecimalField(source='perfil.costo_hora', max_digits=10, decimal_places=2, required=False,
                                          allow_null=True, min_value=0)
    salario_mensual = serializers.DecimalField(source='perfil.salario_mensual', max_digits=12, decimal_places=2,
                                               required=False, allow_null=True, min_value=0)
    nomina = serializers.CharField(source='perfil.nomina', required=False, allow_blank=True, max_length=60)
    puestos_adicionales = serializers.SerializerMethodField()
    puestos_adicionales_ids = serializers.PrimaryKeyRelatedField(
        queryset=PuestoDeTrabajo.objects.all(), many=True, write_only=True, required=False)

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'nombre', 'is_active', 'last_login',
            'password', 'puesto_trabajo_id', 'perfil', 'puesto', 'puesto_id', 'departamento',
            'groups', 'roles', 'roles_asignados', 'horas_semana', 'costo_hora', 'salario_mensual', 'nomina',
            'puestos_adicionales', 'puestos_adicionales_ids',
        ]
        read_only_fields = ['last_login']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'email': {'required': False, 'allow_blank': True},
        }

    def get_nombre(self, obj):
        return obj.get_full_name() or obj.username

    def get_puestos_adicionales(self, obj):
        perfil = getattr(obj, 'perfil', None)
        if perfil is None:
            return []
        return [{'id': p.id, 'nombre': p.nombre, 'departamento': p.departamento.nombre if p.departamento_id else None}
                for p in perfil.puestos_adicionales.select_related('departamento')]

    def validate_puestos_adicionales_ids(self, puestos):
        """Un puesto adicional da el equipo de ese puesto: solo la Dirección lo asigna o lo quita."""
        from apps.desempeno.permisos import es_administrador
        quien = self._quien()
        actuales = set(self.instance.perfil.puestos_adicionales.values_list('pk', flat=True)) \
            if self.instance is not None and hasattr(self.instance, 'perfil') else set()
        if {p.pk for p in puestos} != actuales and quien is not None and not es_administrador(quien):
            raise serializers.ValidationError("Solo la Dirección asigna puestos adicionales.")
        return list(dict.fromkeys(puestos))

    def _puestos_adicionales(self, user, puestos):
        if puestos is None:
            return
        principal = user.perfil.puesto_trabajo_id
        user.perfil.puestos_adicionales.set([p for p in puestos if p.pk != principal])

    def get_roles(self, obj):
        return [g.name for g in obj.groups.all()]

    def validate_username(self, value):
        value = value.strip().lower()
        if not value or ' ' in value:
            raise serializers.ValidationError("El usuario no puede estar vacío ni tener espacios.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if not value:
            return value
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya hay un usuario con ese correo.")
        return value

    def _quien(self):
        r = self.context.get('request')
        return r.user if r else None

    def validate_roles_asignados(self, roles):
        """Mínimo privilegio al dar perfiles: nadie cambia los suyos ni da (o quita) permisos que no tiene."""
        from apps.core.models import PermisosDePerfil
        from apps.core.permisos import permisos
        quien = self._quien()
        validos = {p.grupo.name: set(p.permisos or []) for p in PermisosDePerfil.objects.select_related('grupo')}
        roles = list(dict.fromkeys(r for r in roles if r))
        if not roles:
            raise serializers.ValidationError("Elige al menos un perfil (Colaborador si solo cumple sus tareas).")
        malos = [r for r in roles if r not in validos]
        if malos:
            raise serializers.ValidationError(f"Perfil desconocido: {', '.join(malos)}.")
        if quien is None or quien.is_superuser:
            return roles
        mios = permisos(quien)
        if self.instance is not None and self.instance.pk == quien.pk:
            raise serializers.ValidationError("No puedes cambiar tus propios perfiles de acceso.")
        nuevos = set().union(*(validos[r] for r in roles)) if roles else set()
        if not nuevos <= mios:
            raise serializers.ValidationError("No puedes dar permisos que tú no tienes: " + ', '.join(sorted(nuevos - mios)) + '.')
        if self.instance is not None and not permisos(self.instance) <= mios:
            raise serializers.ValidationError("Esta persona tiene permisos que tú no tienes: sus perfiles los cambia la Dirección.")
        return roles

    def _ve_salarios(self):
        from apps.core.permisos import tiene
        quien = self._quien()
        return quien is None or tiene(quien, 'personal.salarios')

    def to_representation(self, obj):
        d = super().to_representation(obj)
        if not self._ve_salarios():
            for k in ('costo_hora', 'salario_mensual', 'nomina'):
                d[k] = None
        return d

    def validate(self, data):
        if not self._ve_salarios():
            perfil = data.get('perfil') or {}
            for k in ('costo_hora', 'salario_mensual', 'nomina'):
                perfil.pop(k, None)  # quien no maneja salarios no los cambia
        password = data.get('password')
        if self.instance is None and not password:
            raise serializers.ValidationError({"password": "Ponle una contraseña inicial."})
        if password:
            candidato = self.instance or User(username=data.get('username', ''), email=data.get('email', ''),
                                              first_name=data.get('first_name', ''), last_name=data.get('last_name', ''))
            try:
                validate_password(password, candidato)
            except DjangoValidationError as e:
                raise serializers.ValidationError({"password": list(e.messages)})
        return data

    def _roles(self, user, roles):
        user.groups.clear()
        for nombre in roles:
            user.groups.add(Group.objects.get_or_create(name=nombre)[0])
        # El panel de Django solo lo usan los administradores.
        es_admin = 'Administrador' in roles
        if user.is_staff != es_admin and not user.is_superuser:
            user.is_staff = es_admin
            user.save(update_fields=['is_staff'])

    def create(self, validated_data):
        perfil_data = validated_data.pop('perfil', {})
        roles = validated_data.pop('roles_asignados', ['Colaborador'])
        adicionales = validated_data.pop('puestos_adicionales_ids', None)
        user = User.objects.create_user(**validated_data)
        user.perfil.puesto_trabajo = perfil_data.get('puesto_trabajo')
        for campo in PERFIL_EDITABLE[1:]:
            if campo in perfil_data:
                setattr(user.perfil, campo, perfil_data[campo])
        costo_desde_salario(user.perfil, perfil_data)
        self._roles(user, roles or ['Colaborador'])  # antes de guardar el puesto: así el organigrama puede sumar «Supervisor»
        user.perfil.save()
        self._puestos_adicionales(user, adicionales)
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        perfil_data = validated_data.pop('perfil', {})
        if perfil_data:
            perfil, _ = PerfilUsuario.objects.get_or_create(user=instance)
            for campo in PERFIL_EDITABLE:
                if campo in perfil_data:
                    setattr(perfil, campo, perfil_data[campo])
            costo_desde_salario(perfil, perfil_data)
            perfil.save()
        roles = validated_data.pop('roles_asignados', None)
        adicionales = validated_data.pop('puestos_adicionales_ids', None)
        instance = super().update(instance, validated_data)
        if roles is not None:
            self._roles(instance, roles)
        self._puestos_adicionales(instance, adicionales)
        return instance
