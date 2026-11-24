import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';

// Destino del backend. Se puede cambiar con la variable TESSERA_API (p. ej. para otra instancia en otro puerto).
const api = (globalThis as { process?: { env: Record<string, string | undefined> } }).process?.env.TESSERA_API ?? 'http://127.0.0.1:8000';

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: {
      '/api': {
        target: api,
        changeOrigin: true,
      },
    },
  },
  test: { environment: 'node' },
});
