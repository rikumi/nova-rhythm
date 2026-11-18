// npm install --no-save playwright (or set NOVA_PLAYWRIGHT_MODULE to an existing install).
import {createServer} from 'vite';
import {readFileSync,writeFileSync,mkdirSync,existsSync,createReadStream} from 'node:fs';
import {resolve} from 'node:path';
import {pathToFileURL} from 'node:url';
import {execFileSync} from 'node:child_process';
import {createHash} from 'node:crypto';
const root=process.cwd(),runtime=resolve('.build/sharp-depth-layers');
const python=process.env.NOVA_PYTHON||resolve(process.platform==='win32'?'.venv/Scripts/python.exe':'.venv/bin/python');
const requested=process.argv.slice(2);
execFileSync(python,['scripts/sharp/export_depth_layers.py','--prepare',...(requested.length?['--codes',...requested]:[])],{stdio:'inherit'});
const {items}=JSON.parse(readFileSync(resolve(runtime,'plan.json'),'utf8'));
let playwright;
if(process.env.NOVA_PLAYWRIGHT_MODULE)playwright=await import(pathToFileURL(resolve(process.env.NOVA_PLAYWRIGHT_MODULE)).href);
else try{playwright=await import('playwright');}catch(error){
  const cached=resolve('.local/browser-check/node_modules/@playwright/test/index.mjs');
  if(!existsSync(cached))throw Error('Install playwright or set NOVA_PLAYWRIGHT_MODULE',{cause:error});
  playwright=await import(pathToFileURL(cached).href);
}
const {chromium}=playwright;
const server=await createServer({configFile:false,root,cacheDir:resolve(runtime,'vite-cache'),server:{host:'127.0.0.1',port:5181,strictPort:true},plugins:[{
  name:'depth-bake-files',configureServer(server){server.middlewares.use(async(req,res,next)=>{
    const path=req.url?.split('?')[0];
    if(path==='/__depth-bake'){res.setHeader('Content-Type','text/html');res.end('<script type="module" src="/scripts/sharp/render_depth_layers.js"></script>');return;}
    const model=path?.match(/^\/__depth-bake\/model\/(\d{4})\.ply$/);
    if(model){res.setHeader('Content-Type','application/octet-stream');createReadStream(resolve('.build/sharp-layering',model[1],'scene.ply')).pipe(res);return;}
    const frame=path?.match(/^\/__depth-bake\/frame\/(\d{4})\/(reference|\d+)\.rgba$/);
    if(frame&&req.method==='POST'){
      const chunks=[];for await(const chunk of req)chunks.push(chunk);
      const folder=resolve(runtime,frame[1]);mkdirSync(folder,{recursive:true});writeFileSync(resolve(folder,frame[2]+'.rgba'),Buffer.concat(chunks));res.end('ok');return;
    }
    next();
  });}
}]});
await server.listen();
const browser=await chromium.launch({channel:'chrome',headless:true,args:['--disable-background-timer-throttling']});
try {
  const page=await browser.newPage();page.on('pageerror',e=>console.error(e));
  await page.goto('http://127.0.0.1:5181/__depth-bake');await page.waitForFunction(()=>typeof window.bakeDepthLayers==='function');
  for(const [index,item] of items.entries()){
    const report=resolve(runtime,item.code,'layers.json');
    const cached=existsSync(report)?JSON.parse(readFileSync(report,'utf8')):undefined,payload=resolve(runtime,item.code,'scene.layers');
    if(cached?.fingerprint===item.fingerprint&&existsSync(payload)&&createHash('sha256').update(readFileSync(payload)).digest('hex')===cached.sha256){console.log('cached',item.code);continue;}
    console.log(JSON.stringify({state:'rendering',code:item.code,index:index+1,total:items.length}));
    await page.evaluate(item=>window.bakeDepthLayers(item),item);
    execFileSync(python,['scripts/sharp/export_depth_layers.py','--pack',item.code],{stdio:'inherit',maxBuffer:1024*1024});
  }
} finally {await browser.close();await server.close();}
