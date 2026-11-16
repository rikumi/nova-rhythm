import type { Outfit, CardLayer } from './types';

export const CARD_CONTENT_SCALE = .88;
export function backgroundLayer(layer: CardLayer, index: number): boolean {
  return index === 0 || /(?:^|_)(?:bg|background)(?:\d|_|$)/i.test(layer.name);
}
export function cardDepths(card: Outfit['card']): number[] {
  return card.layers.map((layer,index) => (layer.native_z ?? 0) * (layer.projection_factor ?? 1)
    * (card.layout === 'canvas' || backgroundLayer(layer,index) ? 1 : CARD_CONTENT_SCALE) / (card.mask_size || 712));
}
