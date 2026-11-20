// Franja que va primero en la app mientras la persona siga con la contraseña base («usuarios»).
import { useState } from "react";
import { KeyRound } from "lucide-react";
import { cambiarClave } from "@/lib/api";
import { useSesion } from "@/lib/sesion";

const CLAVE_BASE = "usuarios";

export default function AlertaClaveBase() {
  const { usuario, recargar } = useSesion();
  const [abierto, setAbierto] = useState(false);
  const [nueva, setNueva] = useState("");
  const [repetir, setRepetir] = useState("");
  const [error, setError] = useState("");
  const [guardando, setGuardando] = useState(false);
  if (!usuario?.debe_cambiar_clave) return null;

  const guardar = async (e) => {
    e.preventDefault();
    if (nueva !== repetir) { setError("Las dos contraseñas no coinciden."); return; }
    setGuardando(true);
    setError("");
    try {
      await cambiarClave(CLAVE_BASE, nueva);
      await recargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardando(false);
    }
  };

  return (
    <div role="alert" className="border-b border-amarillo-600/40 bg-amarillo-50 px-4 py-3 text-sm text-[#7a5000]">
      <div className="mx-auto flex max-w-[1320px] flex-wrap items-center gap-x-3 gap-y-2">
        <KeyRound className="size-5 shrink-0" aria-hidden />
        <p className="min-w-0 flex-1"><b>Cambia tu contraseña base.</b> Sigues usando la contraseña que te dieron al crear tu cuenta; elige una propia para proteger tu acceso.</p>
        {!abierto && <button type="button" onClick={() => setAbierto(true)} className="rounded-lg bg-azul px-3 py-1.5 font-semibold text-white hover:bg-azul-700">Cambiarla ahora</button>}
      </div>
      {abierto && (
        <form onSubmit={guardar} className="mx-auto mt-3 flex max-w-[1320px] flex-wrap items-start gap-2">
          <input type="password" className="campo !w-auto min-w-48 flex-1" placeholder="Contraseña nueva (mín. 8)" aria-label="Contraseña nueva" autoComplete="new-password" value={nueva} onChange={(e) => setNueva(e.target.value)} required minLength={8} />
          <input type="password" className="campo !w-auto min-w-48 flex-1" placeholder="Repítela" aria-label="Repite la contraseña nueva" autoComplete="new-password" value={repetir} onChange={(e) => setRepetir(e.target.value)} required />
          <button type="submit" disabled={guardando} className="h-10 rounded-lg bg-azul px-4 font-semibold text-white hover:bg-azul-700 disabled:opacity-50">{guardando ? "Guardando…" : "Guardar"}</button>
          {error && <p className="basis-full text-rojo">{error}</p>}
        </form>
      )}
    </div>
  );
}
