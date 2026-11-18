import type { Outfit, CardLayer } from './types';

export function backgroundLayer(layer: CardLayer, index: number): boolean {
  return index === 0 || /(?:^|_)(?:bg|background)(?:\d|_|$)/i.test(layer.name);
}

export function cardDepths(card: Outfit['card']): number[] {
  // RectTransform depth and its native perspective projection use Canvas pixels.
  return card.layers.map(layer => (layer.native_z ?? 0) * (layer.projection_factor ?? 1) / (card.mask_size || 712));
}
