import { androidBottomInset } from './safeArea';

const display=window.matchMedia('(display-mode: standalone), (display-mode: fullscreen)');
const probe=document.createElement('div');
probe.dataset.safeAreaProbe='true';
probe.style.cssText='position:fixed;visibility:hidden;pointer-events:none;width:0;height:0;padding-bottom:env(safe-area-inset-bottom,0px);margin-bottom:env(safe-area-max-inset-bottom,0px)';
document.body.append(probe);
const heights=new Map<string,number>();
let scheduled=0;
const updateDisplay=()=>{
  const ios=(navigator as Navigator & {standalone?:boolean}).standalone;
  document.documentElement.dataset.display=display.matches || ios ? 'standalone' : 'browser';
  updateBottomInset();
};
function updateBottomInset() {
  const viewport=window.visualViewport;
  const orientation=screen.orientation?.type || (screen.width<=screen.height ? 'portrait' : 'landscape');
  const fullHeight=Math.max(heights.get(orientation)||0,window.innerHeight);
  heights.set(orientation,fullHeight);
  const active=document.activeElement;
  const editing=active instanceof HTMLInputElement || active instanceof HTMLTextAreaElement || active instanceof HTMLElement && active.isContentEditable;
  const style=getComputedStyle(probe);
  const result=androidBottomInset({
    installed:document.documentElement.dataset.display==='standalone',android:/Android/i.test(navigator.userAgent),
    native:parseFloat(style.paddingBottom)||0,maximum:parseFloat(style.marginBottom)||0,
    viewportHeight:window.innerHeight,visualHeight:viewport?.height ?? window.innerHeight,
    visualTop:viewport?.offsetTop||0,scale:viewport?.scale||1,
    screenY:window.screenY,screenHeight:screen.height,availableTop:(screen as Screen & {availTop?:number}).availTop||0,availableHeight:screen.availHeight,
    keyboardOpen:editing && (window.innerHeight-(viewport?.height ?? window.innerHeight)>120 || fullHeight-window.innerHeight>120),
  });
  const value=`${result.bottom}px`;
  if(document.documentElement.style.getPropertyValue('--pwa-bottom-inset')!==value)document.documentElement.style.setProperty('--pwa-bottom-inset',value);
  document.documentElement.dataset.bottomInsetSource=result.source;
}
const scheduleInset=()=>{
  if(scheduled)return;
  scheduled=requestAnimationFrame(()=>{scheduled=0;updateBottomInset();});
};
updateDisplay();display.addEventListener('change',updateDisplay);
window.addEventListener('resize',scheduleInset);
window.addEventListener('orientationchange',scheduleInset);
window.addEventListener('pageshow',scheduleInset);
window.visualViewport?.addEventListener('resize',scheduleInset);
window.visualViewport?.addEventListener('scroll',scheduleInset);
document.addEventListener('focusin',scheduleInset);
document.addEventListener('focusout',scheduleInset);
document.addEventListener('visibilitychange',()=>{if(!document.hidden)scheduleInset();});
// Installed Chrome sometimes delivers its native insets after the first frame.
for(const delay of [100,350,1000])setTimeout(scheduleInset,delay);
if(import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load',()=>{
    void navigator.serviceWorker.register('/sw.js',{updateViaCache:'none'}).catch(()=>{/* Installation remains optional. */});
  });
}
