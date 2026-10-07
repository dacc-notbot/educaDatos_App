import { loadEnv } from 'vite';

const base = (process.env.VITE_API_BASE_URL || loadEnv('production', process.cwd(), 'VITE_').VITE_API_BASE_URL || '').trim();
try {
  if (!base) throw new Error('Falta VITE_API_BASE_URL: configura la dirección pública de Cloud Run antes de publicar.');
  const url = new URL(base);
  if (url.protocol !== 'https:' || ['localhost', '127.0.0.1', '[::1]'].includes(url.hostname) || /\.(web\.app|firebaseapp\.com|invalid)$/.test(url.hostname) || url.username || url.password || url.search || url.hash) {
    throw new Error('VITE_API_BASE_URL debe ser la dirección HTTPS pública del backend, sin contraseñas ni parámetros.');
  }
  const response = await fetch(`${base.replace(/\/$/, '')}/health`, { signal: AbortSignal.timeout(20000) });
  if (!response.ok || (await response.json()).status !== 'ok') throw new Error('El backend no confirmó que está disponible. Revisa el servicio en Cloud Run.');
  console.log('Backend público verificado. La web puede compilarse y publicarse.');
} catch (error) {
  console.error(error instanceof Error ? error.message : 'No se pudo verificar el backend público.');
  process.exitCode = 1;
}
