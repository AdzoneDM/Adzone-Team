import { useState } from "react";
import { cambiarClave, cambiarClaveEquipo } from "@/lib/api";
import { useSesion } from "@/lib/sesion";
import { Alerta, Avatar, Boton, Cabecera, Campo, Panel, useAviso } from "@/components/ui";

export default function MiCuenta() {
  const { usuario, esAdmin } = useSesion();
  const avisar = useAviso();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [repetir, setRepetir] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  const enviar = async (e) => {
    e.preventDefault();
    setError("");
    if (nueva.length < 8) return setError("La contraseña nueva necesita al menos 8 caracteres.");
    if (nueva !== repetir) return setError("Las dos contraseñas nuevas no coinciden.");
    setGuardando(true);
    try {
      await cambiarClave(actual, nueva);
      setActual(""); setNueva(""); setRepetir("");
      avisar("Contraseña cambiada.");
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };

  return (
    <div className="max-w-2xl space-y-6">
      <Cabecera titulo="Mi cuenta" />
      <Panel>
        <div className="flex items-center gap-4">
          <Avatar nombre={usuario.nombre} tam="lg" />
          <div>
            <p className="font-display text-xl font-semibold text-noche">{usuario.nombre}</p>
            <p className="text-gris">{usuario.puesto || "Sin puesto asignado"}{usuario.departamento ? ` · ${usuario.departamento}` : ""}</p>
            <p className="text-sm text-gris">{usuario.username} · {usuario.email}</p>
          </div>
        </div>
      </Panel>
      <Panel titulo="Cambiar contraseña">
        <form onSubmit={enviar} className="space-y-4">
          {error && <Alerta>{error}</Alerta>}
          <Campo etiqueta="Contraseña actual">{(id) => <input id={id} type="password" className="campo" value={actual} onChange={(e) => setActual(e.target.value)} autoComplete="current-password" />}</Campo>
          <Campo etiqueta="Contraseña nueva" ayuda="Al menos 8 caracteres, que no sea solo números ni se parezca a tu nombre.">{(id) => <input id={id} type="password" className="campo" value={nueva} onChange={(e) => setNueva(e.target.value)} autoComplete="new-password" />}</Campo>
          <Campo etiqueta="Repite la contraseña nueva">{(id) => <input id={id} type="password" className="campo" value={repetir} onChange={(e) => setRepetir(e.target.value)} autoComplete="new-password" />}</Campo>
          <Boton type="submit" cargando={guardando}>Cambiar contraseña</Boton>
        </form>
      </Panel>
      {esAdmin && <ClaveEquipo />}
    </div>
  );
}

/** La clave general que se pide en la entrada antes de elegir área y persona. Solo el administrador la cambia. */
function ClaveEquipo() {
  const avisar = useAviso();
  const [nueva, setNueva] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);

  const enviar = async (e) => {
    e.preventDefault();
    setError("");
    if (nueva.length < 8) return setError("La clave del equipo necesita al menos 8 caracteres.");
    setGuardando(true);
    try {
      await cambiarClaveEquipo(nueva);
      setNueva("");
      avisar("Clave del equipo guardada. Compártela con el equipo.");
    } catch (err) { setError(err.message); }
    setGuardando(false);
  };

  return (
    <Panel titulo="Clave general del equipo">
      <form onSubmit={enviar} className="space-y-4">
        <p className="text-sm text-gris">Se pide al entrar, antes de elegir el área y la persona. No entra como nadie: solo muestra el directorio en ese dispositivo. Los dispositivos que ya la escribieron no la vuelven a pedir.</p>
        {error && <Alerta>{error}</Alerta>}
        <Campo etiqueta="Clave nueva" ayuda="Al menos 8 caracteres.">{(id) => <input id={id} type="password" className="campo" value={nueva} onChange={(e) => setNueva(e.target.value)} autoComplete="new-password" />}</Campo>
        <Boton type="submit" cargando={guardando}>Guardar clave del equipo</Boton>
      </form>
    </Panel>
  );
}
