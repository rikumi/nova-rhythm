import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
export default defineConfig({
  plugins: [react()],
  base: '/',
  publicDir: process.env.NOVA_PUBLIC_DIR || 'public',
  build: { sourcemap: false, outDir: process.env.NOVA_DIST_DIR || 'dist' },
});
