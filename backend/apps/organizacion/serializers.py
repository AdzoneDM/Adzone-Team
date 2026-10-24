from django.contrib.auth.models import Group, User
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from .models import PerfilUsuario, PuestoDeTrabajo

ROLES = ['Administrador', 'Gerente de Departamento', 'Colaborador']


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
            'funciones_principales', 'personas', 'subordinados',
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
    roles_asignados = serializers.ListField(
        child=serializers.ChoiceField(choices=ROLES), write_only=True, required=False
    )
    nombre = serializers.SerializerMethodField()
    puesto = serializers.CharField(source='perfil.puesto_trabajo.nombre', read_only=True, default=None)
    puesto_id = serializers.IntegerField(source='perfil.puesto_trabajo_id', read_only=True, default=None)
    departamento = serializers.CharField(source='perfil.puesto_trabajo.departamento.nombre', read_only=True, default=None)
    roles = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'nombre', 'is_active', 'last_login',
            'password', 'puesto_trabajo_id', 'perfil', 'puesto', 'puesto_id', 'departamento',
            'groups', 'roles', 'roles_asignados',
        ]
        read_only_fields = ['last_login']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
            'email': {'required': True},
        }

    def get_nombre(self, obj):
        return obj.get_full_name() or obj.username

    def get_roles(self, obj):
        return [g.name for g in obj.groups.all()]

    def validate_username(self, value):
        value = value.strip().lower()
        if not value or ' ' in value:
            raise serializers.ValidationError("El usuario no puede estar vacío ni tener espacios.")
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        qs = User.objects.filter(email__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("Ya hay un usuario con ese correo.")
        return value

    def validate(self, data):
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
        puesto = validated_data.pop('perfil', {}).get('puesto_trabajo')
        roles = validated_data.pop('roles_asignados', ['Colaborador'])
        user = User.objects.create_user(**validated_data)
        user.perfil.puesto_trabajo = puesto
        user.perfil.save()
        self._roles(user, roles or ['Colaborador'])
        return user

    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        perfil_data = validated_data.pop('perfil', {})
        if 'puesto_trabajo' in perfil_data:
            perfil, _ = PerfilUsuario.objects.get_or_create(user=instance)
            perfil.puesto_trabajo = perfil_data['puesto_trabajo']
            perfil.save()
        roles = validated_data.pop('roles_asignados', None)
        instance = super().update(instance, validated_data)
        if roles is not None:
            self._roles(instance, roles)
        return instance
