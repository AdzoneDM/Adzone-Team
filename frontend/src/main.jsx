import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource-variable/inter";
import "@fontsource-variable/outfit";
import "./index.css";
import App from "@/app/App";
import { SesionProvider } from "@/lib/sesion";
import { vigilarActualizaciones } from "@/lib/actualizacion";
import { AvisosProvider, ConfirmarProvider } from "@/components/ui";
import { VisorProvider } from "@/components/VisorImagen";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <SesionProvider>
        <AvisosProvider>
          <ConfirmarProvider>
            <VisorProvider>
              <App />
            </VisorProvider>
          </ConfirmarProvider>
        </AvisosProvider>
      </SesionProvider>
    </BrowserRouter>
  </StrictMode>
);

// Instalable en el celular (PWA). Solo en producción: en desarrollo el caché estorba.
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    // updateViaCache "none": el navegador siempre pide el sw.js nuevo (no el guardado), así la app instalada se actualiza sola
    navigator.serviceWorker.register("/sw.js", { updateViaCache: "none" }).catch(() => {});
    vigilarActualizaciones();
  });
  // «Instalar la app» (Android/Chrome): se guarda el aviso del navegador para ofrecerlo cuando convenga
  window.addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    window.__instalarApp = e;
    window.dispatchEvent(new Event("adzone:instalable"));
  });
}
