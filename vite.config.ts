import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { createReadStream, existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
export default defineConfig({
  plugins: [react(), {
    name: 'local-layering-preview',
    apply: 'serve',
    configureServer(server) {
      const trialRoot = resolve('.build/layering-trial');
      server.middlewares.use((request, response, next) => {
        const path = request.url?.split('?')[0];
        const image = path?.match(/^\/__(layering-trial|sharp-layering)\/(\d{4})\/(layer-\d{2}\.(?:png|webp))$/);
        if (image) {
          const file = resolve('.build', image[1], image[2], image[3]);
          if (!existsSync(file)) return next();
          response.setHeader('Content-Type', image[3].endsWith('.webp') ? 'image/webp' : 'image/png');
          response.setHeader('Cache-Control', 'no-store');
          createReadStream(file).pipe(response);
          return;
        }
        const manifest = resolve(trialRoot, 'local-overrides.json');
        if (path !== '/data/experimental-layering.json' || !existsSync(manifest)) return next();
        try {
          const overrides = JSON.parse(readFileSync(manifest, 'utf8'));
          response.setHeader('Content-Type', 'application/json; charset=utf-8');
          response.setHeader('Cache-Control', 'no-store');
          response.end(JSON.stringify({ schemaVersion: 1, outfits: overrides }));
        } catch (error) { next(error); }
      });
    },
  }],
  base: '/',
  publicDir: process.env.NOVA_PUBLIC_DIR || 'public',
  server: { watch: { ignored: ['**/.build/**', '**/.local/**', '**/.venv/**', '**/tools/**'] } },
  build: { sourcemap: false, outDir: process.env.NOVA_DIST_DIR || 'dist' },
});
