import type { Outfit, CardLayer } from './types';

export const CARD_CONTENT_SCALE = .88;
// Peak screen-space separation in the calibrated SHARP batch (p01–p99),
// measured at full pointer input in the square artwork window. Native Z uses
// different units, so cap its projected motion rather than comparing raw Z.
export const MAX_NATIVE_PARALLAX = { x: .052, y: .036 } as const;
export function backgroundLayer(layer: CardLayer, index: number): boolean {
  return index === 0 || /(?:^|_)(?:bg|background)(?:\d|_|$)/i.test(layer.name);
}
export function cardDepths(card: Outfit['card']): number[] {
  const depths = card.layers.map((layer,index) => (layer.native_z ?? 0) * (layer.projection_factor ?? 1)
    * (card.layout === 'canvas' || backgroundLayer(layer,index) ? 1 : CARD_CONTENT_SCALE) / (card.mask_size || 712));
  if (card.layout === 'canvas' || depths.length < 2) return depths;
  const span = Math.max(...depths) - Math.min(...depths);
  if (!span) return depths;
  const motion = card.motion || { rotation_x: 3, rotation_y: -8 };
  const horizontal = span * Math.abs(Math.sin(motion.rotation_y * Math.PI / 180));
  const vertical = span * Math.abs(Math.sin(motion.rotation_x * Math.PI / 180));
  const scale = Math.min(1, horizontal ? MAX_NATIVE_PARALLAX.x / horizontal : 1,
    vertical ? MAX_NATIVE_PARALLAX.y / vertical : 1);
  return scale < 1 ? depths.map(depth => depth * scale) : depths;
}
