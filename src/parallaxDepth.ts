import type { Outfit, CardLayer } from './types';

export const CARD_CONTENT_SCALE = .88;
export const DEPTH_SPAN_GAIN = .9;
export function backgroundLayer(layer: CardLayer, index: number): boolean {
  return index === 0 || /(?:^|_)(?:bg|background)(?:\d|_|$)/i.test(layer.name);
}
function originalDepths(card: Outfit['card']): number[] {
  return card.layers.map((layer,index) => (layer.native_z ?? 0) * (layer.projection_factor ?? 1)
    * (card.layout === 'canvas' || backgroundLayer(layer,index) ? 1 : CARD_CONTENT_SCALE) / (card.mask_size || 712));
}
export function normalizedDepthTarget(outfits: Outfit[]): number {
  const spans = outfits.filter(outfit => outfit.card.layout !== 'canvas' && outfit.card.layers.length > 1)
    .map(outfit => { const depths=originalDepths(outfit.card); return Math.max(...depths)-Math.min(...depths); })
    .filter(span => span > 0);
  return (spans.length ? spans.reduce((sum,span)=>sum+span,0)/spans.length : 1.8) * DEPTH_SPAN_GAIN;
}
export function normalizedDepths(card: Outfit['card'], target: number): number[] {
  const original=originalDepths(card);
  if (original.length < 2) return original.map(()=>0);
  const near=Math.min(...original), far=Math.max(...original), span=far-near;
  if (!span) return original.map(()=>0);
  return original.map(value=>((value-near)/span-.5)*target);
}
