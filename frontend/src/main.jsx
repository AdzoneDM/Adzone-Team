import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import "@fontsource-variable/inter";
import "@fontsource-variable/outfit";
import "./index.css";
import App from "@/app/App";
import { SesionProvider } from "@/lib/sesion";
import { AvisosProvider, ConfirmarProvider } from "@/components/ui";

createRoot(document.getElementById("root")).render(
  <StrictMode>
    <BrowserRouter>
      <SesionProvider>
        <AvisosProvider>
          <ConfirmarProvider>
            <App />
          </ConfirmarProvider>
        </AvisosProvider>
      </SesionProvider>
    </BrowserRouter>
  </StrictMode>
);

// Instalable en el celular (PWA). Solo en producción: en desarrollo el caché estorba.
if ("serviceWorker" in navigator && import.meta.env.PROD) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {});
  });
}
