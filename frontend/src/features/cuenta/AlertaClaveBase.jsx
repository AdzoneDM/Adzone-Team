// Franja que va primero en la app mientras la persona siga con la contraseña base («usuarios»).
import { useState } from "react";
import { KeyRound } from "lucide-react";
import { cambiarClave } from "@/lib/api";
import { useSesion } from "@/lib/sesion";

const CLAVE_BASE = "usuarios";

export default function AlertaClaveBase() {
  const { usuario, recargar } = useSesion();
  const [actual, setActual] = useState("");
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
      await cambiarClave(actual || CLAVE_BASE, nueva);
      await recargar();
    } catch (err) {
      setError(err.message);
    } finally {
      setGuardando(false);
    }
  };

  // Obligatorio: mientras tenga la contraseña base, el servidor no deja usar nada más (cualquiera que conozca la base podría entrar)
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-noche/95 p-4" role="dialog" aria-modal="true" aria-labelledby="clave-base-titulo">
      <form onSubmit={guardar} className="w-full max-w-md space-y-4 rounded-2xl bg-white p-6 shadow-2xl">
        <div className="flex items-center gap-3">
          <span className="flex size-11 shrink-0 items-center justify-center rounded-xl bg-amarillo-50 text-[#a86a00]"><KeyRound className="size-6" aria-hidden /></span>
          <h2 id="clave-base-titulo" className="text-xl font-semibold">Crea tu contraseña</h2>
        </div>
        <p className="text-sm text-gris">Entraste con una contraseña que te dieron (la de las cuentas nuevas o una temporal). Para proteger tu cuenta, elige una propia: sin esto no se puede usar la plataforma.</p>
        <input type="password" className="campo" placeholder="La contraseña con la que entraste" aria-label="Contraseña con la que entraste" autoComplete="current-password" value={actual} onChange={(e) => setActual(e.target.value)} required />
        <input type="password" className="campo" placeholder="Contraseña nueva (mín. 8)" aria-label="Contraseña nueva" autoComplete="new-password" value={nueva} onChange={(e) => setNueva(e.target.value)} required minLength={8} />
        <input type="password" className="campo" placeholder="Repítela" aria-label="Repite la contraseña nueva" autoComplete="new-password" value={repetir} onChange={(e) => setRepetir(e.target.value)} required />
        <p className="text-xs text-gris">Al menos 8 caracteres, que no sea solo números ni se parezca a tu nombre.</p>
        {error && <p className="text-sm text-rojo">{error}</p>}
        <button type="submit" disabled={guardando} className="h-11 w-full rounded-lg bg-azul font-semibold text-white hover:bg-azul-700 disabled:opacity-50">{guardando ? "Guardando…" : "Guardar y entrar"}</button>
      </form>
    </div>
  );
}
