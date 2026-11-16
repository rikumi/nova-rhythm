export interface BottomInsetMetrics {
  installed: boolean; android: boolean; native: number; maximum: number;
  viewportHeight: number; visualHeight: number; visualTop: number; scale: number;
  screenY: number; screenHeight: number; availableTop: number; availableHeight: number;
  keyboardOpen: boolean;
}

/** Geometry can supplement missing Android insets; 32px is a guard, not a measurement. */
export function androidBottomInset(metrics: BottomInsetMetrics): { bottom: number; source: string } {
  if(!metrics.installed || !metrics.android)return {bottom:0,source:'native-css'};
  if(metrics.keyboardOpen)return {bottom:0,source:'keyboard'};
  const bounded=(value:number)=>Number.isFinite(value) && value>0 && value<=96 ? value : 0;
  const native=bounded(metrics.native),maximum=bounded(metrics.maximum);
  if(native || maximum)return {bottom:Math.max(native,maximum),source:maximum>native ? 'maximum-inset' : 'native-inset'};
  if(Math.abs(metrics.scale-1)<.02) {
    const visual=bounded(metrics.viewportHeight-metrics.visualHeight-metrics.visualTop);
    if(visual)return {bottom:Math.ceil(visual),source:'visual-viewport'};
    if(metrics.availableHeight>0 && metrics.availableHeight<metrics.screenHeight && metrics.screenY>=0) {
      const bottom=metrics.screenY+metrics.viewportHeight;
      const screen=bounded(bottom-metrics.availableTop-metrics.availableHeight);
      if(bottom<=metrics.screenHeight+2 && screen)return {bottom:Math.ceil(screen),source:'screen-available'};
    }
  }
  return {bottom:32,source:'android-pwa-fallback'};
}
