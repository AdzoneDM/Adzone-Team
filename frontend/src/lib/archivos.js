// Límites de los archivos que se suben como evidencia. El de los videos lo manda el servidor (según lo que permita el servidor web).
export const MAX_FOTO_MB = 10; // fotos y PDF
// videoMB y zipMB: lo que cabe en una sola petición (el chat). adjuntoGrandeMB y videoGrandeMB: adjuntos de tareas, que se suben
// por partes (lib/subidaPorPartes.js) y por eso pasan los 64 MB del servidor web. Todos llegan con la sesión.
export const limites = { videoMB: 60, zipMB: 50, adjuntoGrandeMB: 400, videoGrandeMB: 400 };
export const fijarLimiteVideo = (mb) => { if (Number(mb) > 0) limites.videoMB = Number(mb); };
export const fijarLimiteZip = (mb) => { if (Number(mb) > 0) limites.zipMB = Number(mb); };
export const fijarLimitesGrandes = ({ limite_adjunto_grande_mb: zip, limite_video_grande_mb: video } = {}) => {
  if (Number(zip) > 0) limites.adjuntoGrandeMB = Number(zip);
  if (Number(video) > 0) limites.videoGrandeMB = Number(video);
};
