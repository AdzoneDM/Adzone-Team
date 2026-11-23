// Límites de los archivos que se suben como evidencia. El de los videos lo manda el servidor (según lo que permita el servidor web).
export const MAX_FOTO_MB = 10; // fotos y PDF
export const limites = { videoMB: 60 };
export const fijarLimiteVideo = (mb) => { if (Number(mb) > 0) limites.videoMB = Number(mb); };
