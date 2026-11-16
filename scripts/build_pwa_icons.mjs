/** Render native game UI assets as an SVG composition, then export install icons. */
import { readFile, mkdir } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import { chromium } from '@playwright/test';
const root=new URL('../',import.meta.url);
const embed=async name=>'data:image/png;base64,'+(await readFile(new URL('public/ui/'+name,root))).toString('base64');
const [paper,outfit]=await Promise.all(['btn_outfit_music.png','home-btn_main_system_outfit_L.png'].map(embed));
// The nested viewBox removes the original button border and its inner shadow. The foreground fits well
// inside the maskable icon's central safe circle, even on circular launchers.
const svg=`<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512">
<rect width="512" height="512" fill="#fafafa"/>
<svg width="512" height="512" viewBox="11 11 154 116" preserveAspectRatio="none"><image href="${paper}" width="176" height="151"/></svg>
<image href="${outfit}" x="128" y="128" width="256" height="256"/>
</svg>`;
const browser=await chromium.launch({channel:process.env.PWA_ICON_BROWSER || 'chrome',headless:true});
const page=await browser.newPage({deviceScaleFactor:1});
const output=new URL('public/icons/',root);await mkdir(output,{recursive:true});
for(const size of [32,180,192,512]) {
  await page.setViewportSize({width:size,height:size});
  await page.setContent(`<html><style>*{margin:0}img{display:block;width:100vw;height:100vh}</style><img src="data:image/svg+xml;base64,${Buffer.from(svg).toString('base64')}"></html>`);
  await page.locator('img').evaluate(img=>img.decode());
  await page.screenshot({path:fileURLToPath(new URL(`icon-${size}.png`,output))});
}
await browser.close();
console.log('Rendered four install icons from the borderless native button and outfit entrance icon.');
