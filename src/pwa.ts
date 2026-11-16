const display=window.matchMedia('(display-mode: standalone), (display-mode: fullscreen)');
const updateDisplay=()=>{
  const ios=(navigator as Navigator & {standalone?:boolean}).standalone;
  document.documentElement.dataset.display=display.matches || ios ? 'standalone' : 'browser';
};
updateDisplay();display.addEventListener('change',updateDisplay);
if(import.meta.env.PROD && 'serviceWorker' in navigator) {
  window.addEventListener('load',()=>{
    void navigator.serviceWorker.register('/sw.js',{updateViaCache:'none'}).catch(()=>{/* Installation remains optional. */});
  });
}
