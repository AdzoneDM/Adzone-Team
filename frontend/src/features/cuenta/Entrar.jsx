import { useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { Eye, EyeOff } from "lucide-react";
import Marca from "@/components/Marca";
import { Alerta, Boton, TiraMes } from "@/components/ui";
import { useSesion } from "@/lib/sesion";

export default function Entrar() {
  const { login } = useSesion();
  const navigate = useNavigate();
  const location = useLocation();
  const [identificador, setIdentificador] = useState("");
  const [clave, setClave] = useState("");
  const [ver, setVer] = useState(false);
  const [recordar, setRecordar] = useState(true);
  const [error, setError] = useState("");
  const [enviando, setEnviando] = useState(false);

  const enviar = async (e) => {
    e.preventDefault();
    setError("");
    if (!identificador.trim() || !clave) {
      setError("Escribe tu usuario (o correo) y tu contraseña.");
      return;
    }
    setEnviando(true);
    try {
      await login(identificador.trim(), clave, recordar);
      navigate(location.state?.desde || "/", { replace: true });
    } catch (err) {
      setError(err.message);
      setEnviando(false);
    }
  };

  return (
    <div className="grid min-h-dvh md:grid-cols-[minmax(0,1fr)_minmax(0,1.1fr)]">
      <aside className="relative hidden flex-col justify-between overflow-hidden bg-noche p-12 text-white md:flex">
        <Marca className="text-xl" />
        <div className="max-w-md">
          <p className="font-display text-[40px] font-semibold leading-[1.1] tracking-tight">
            Cada tarea validada suma a tu mes.
          </p>
          <p className="mt-4 text-lg text-white/70">
            Tus tareas, las entregas de tu equipo, los KPIs de tu puesto y el Empleado del Mes, en un solo lugar.
          </p>
          <div className="mt-10 max-w-sm">
            <TiraMes validadas={11} revision={2} vencidas={1} pendientes={6} oscuro />
            <p className="mt-2 text-sm text-white/60">Así se ve el avance de un mes: amarillo es trabajo validado.</p>
          </div>
        </div>
        <p className="text-sm text-white/50">ADZONE · Creatividad para Marcas Empoderadas</p>
      </aside>

      <main className="flex flex-col justify-center px-6 py-10 sm:px-12">
        <div className="mx-auto w-full max-w-sm">
          <Marca oscuro={false} className="mb-10 text-lg md:hidden" />
          <h1 className="text-3xl font-semibold">Entrar</h1>
          <p className="mt-1 text-gris">Usa tu usuario o tu correo de ADZONE.</p>

          <form onSubmit={enviar} className="mt-8 space-y-5" noValidate>
            {error && <Alerta>{error}</Alerta>}
            <div>
              <label htmlFor="identificador" className="etiqueta">Usuario o correo</label>
              <input id="identificador" name="identifier" className="campo" autoComplete="username" autoCapitalize="none"
                value={identificador} onChange={(e) => setIdentificador(e.target.value)} autoFocus />
            </div>
            <div>
              <label htmlFor="clave" className="etiqueta">Contraseña</label>
              <div className="relative">
                <input id="clave" name="password" type={ver ? "text" : "password"} className="campo pr-11" autoComplete="current-password"
                  value={clave} onChange={(e) => setClave(e.target.value)} />
                <button type="button" onClick={() => setVer((v) => !v)} className="absolute inset-y-0 right-0 flex w-11 items-center justify-center text-gris hover:text-azul"
                  aria-label={ver ? "Ocultar contraseña" : "Mostrar contraseña"}>
                  {ver ? <EyeOff className="size-4" /> : <Eye className="size-4" />}
                </button>
              </div>
            </div>
            <label className="flex items-center gap-2.5 text-sm text-tinta">
              <input type="checkbox" checked={recordar} onChange={(e) => setRecordar(e.target.checked)} className="size-4 rounded accent-azul" />
              Mantener la sesión abierta en este equipo (7 días)
            </label>
            <Boton type="submit" tam="lg" className="w-full" cargando={enviando}>Entrar</Boton>
          </form>
          <p className="mt-8 text-sm text-gris">¿Olvidaste tu contraseña? Pídele a un administrador de ADZONE que te asigne una nueva.</p>
        </div>
      </main>
    </div>
  );
}
