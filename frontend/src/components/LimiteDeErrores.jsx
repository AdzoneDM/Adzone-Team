// Si una pantalla falla al cargarse o al dibujarse, en vez de dejarla en blanco se muestra qué hacer.
import { Component } from "react";
import { RefreshCw, TriangleAlert } from "lucide-react";

export default class LimiteDeErrores extends Component {
  state = { error: null };

  static getDerivedStateFromError(error) { return { error }; }

  componentDidCatch(error) { console.error("Error en la pantalla:", error); }

  // Al ir a otra pantalla (cambia `claveReinicio`) se vuelve a intentar, sin recargar todo
  componentDidUpdate(anterior) {
    if (this.state.error && anterior.claveReinicio !== this.props.claveReinicio) this.setState({ error: null });
  }

  render() {
    if (!this.state.error) return this.props.children;
    const archivo = this.state.error?.deVersionNueva === true || /dynamically imported module|module script|MIME type|Importing a module script failed|Loading chunk|Failed to fetch/i.test(String(this.state.error?.message || this.state.error));
    return (
      <div role="alert" className="mx-auto mt-10 max-w-md rounded-2xl border border-linea bg-white p-8 text-center shadow-sm">
        <span className="mx-auto flex size-14 items-center justify-center rounded-full bg-amarillo-50 text-[#a86a00]"><TriangleAlert className="size-7" aria-hidden /></span>
        <h2 className="mt-4 text-xl font-semibold text-tinta">{archivo ? "Hay una versión nueva de Adzone Team" : "No se pudo abrir esta pantalla"}</h2>
        <p className="mt-2 text-[15px] text-gris">
          {archivo ? "Recarga la página para traer la versión más reciente. No pierdes nada de lo que ya está guardado." : "Prueba de nuevo. Si vuelve a pasar, avísale a Tecnología con lo que estabas haciendo."}
        </p>
        <div className="mt-6 flex justify-center gap-2">
          <button type="button" onClick={() => window.location.reload()} className="inline-flex h-11 items-center gap-2 rounded-lg bg-azul px-5 text-sm font-semibold text-white hover:bg-azul-700">
            <RefreshCw className="size-4" aria-hidden />Recargar la página
          </button>
          {!archivo && <button type="button" onClick={() => this.setState({ error: null })} className="h-11 rounded-lg border border-linea bg-white px-4 text-sm font-medium text-tinta hover:bg-fondo">Reintentar</button>}
        </div>
      </div>
    );
  }
}
