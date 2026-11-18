import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { createReadStream, existsSync, readFileSync, statSync } from 'node:fs';
import { resolve } from 'node:path';
export default defineConfig({
  plugins: [react(), {
    name: 'local-layering-preview',
    apply: 'serve',
    configureServer(server) {
      const trialRoot = resolve('.build/layering-trial');
      server.middlewares.use((request, response, next) => {
        const path = request.url?.split('?')[0];
        if(path==='/data/sharp-scenes.json'){
          const manifest=JSON.parse(readFileSync(resolve('public/data/sharp-scenes.json'),'utf8'));
          for(const [code,info] of Object.entries(manifest.outfits) as [string,Record<string,unknown>][]){
            const file=resolve('.build/sharp-depth-layers',code,'layers.json');if(!existsSync(file))continue;
            const layers=JSON.parse(readFileSync(file,'utf8'));
            if(layers.source_scene_sha256===info.scene_sha256)info.layer_scene={url:`/__sharp-depth-layers/${code}/scene.layers`,bytes:layers.bytes,sha256:layers.sha256,layer_count:20};
          }
          response.setHeader('Content-Type','application/json');response.setHeader('Cache-Control','no-store');response.end(JSON.stringify(manifest));return;
        }
        const depthLayer=path?.match(/^\/__sharp-depth-layers\/(\d{4})\/scene\.layers$/);
        if(depthLayer){
          const file=resolve('.build/sharp-depth-layers',depthLayer[1],'scene.layers');
          if(!existsSync(file))return next();
          response.setHeader('Content-Type','application/octet-stream');response.setHeader('Content-Length',statSync(file).size);
          response.setHeader('Cache-Control','no-store');createReadStream(file).pipe(response);return;
        }
        const sharpScene=path?.match(/^\/__sharp-3d\/(\d{4})\/(scene\.(?:ply(?:\.gz)?|json))$/);
        if(sharpScene){
          const file=resolve('.build/sharp-layering',sharpScene[1],sharpScene[2]);
          if(!existsSync(file))return next();
          const layerMetadata=resolve('.build/sharp-depth-layers',sharpScene[1],'layers.json');
          if(sharpScene[2]==='scene.json'&&existsSync(layerMetadata)){
            const info=JSON.parse(readFileSync(file,'utf8')),layers=JSON.parse(readFileSync(layerMetadata,'utf8'));
            if(layers.source_scene_sha256===info.scene_sha256)info.layer_scene={url:`/__sharp-depth-layers/${sharpScene[1]}/scene.layers`,bytes:layers.bytes,sha256:layers.sha256,layer_count:20};
            response.setHeader('Content-Type','application/json');response.setHeader('Cache-Control','no-store');response.end(JSON.stringify(info));return;
          }
          response.setHeader('Content-Type',file.endsWith('.json')?'application/json; charset=utf-8':'application/octet-stream');
          response.setHeader('Content-Length',statSync(file).size);
          response.setHeader('Cache-Control','no-store');
          if(request.method==='HEAD'){response.end();return;}
          createReadStream(file).pipe(response);return;
        }
        const image = path?.match(/^\/__(layering-trial|layering-hd|sharp-layering)\/(\d{4})\/(layer-\d{2}\.(?:png|webp))$/);
        if (image) {
          const file = resolve('.build', image[1], image[2], image[3]);
          if (!existsSync(file)) return next();
          response.setHeader('Content-Type', image[3].endsWith('.webp') ? 'image/webp' : 'image/png');
          response.setHeader('Cache-Control', 'no-store');
          createReadStream(file).pipe(response);
          return;
        }
        const hdManifest = resolve('.build/layering-hd/local-overrides.json');
        const manifest = existsSync(hdManifest) ? hdManifest : resolve(trialRoot, 'local-overrides.json');
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
