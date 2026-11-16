import type { Outfit } from './types';

interface OutfitCatalog { schemaVersion: number; items: Outfit[]; }
export interface ExperimentalLayeringManifest {
  schemaVersion: number;
  outfits: Record<string, Outfit['card']>;
}

export async function loadOutfits(href: string, fetcher: typeof fetch = fetch): Promise<OutfitCatalog> {
  const response = await fetcher('/data/outfits.json');
  if (!response.ok) throw new Error('秘纹档案暂时无法读取');
  const catalog = await response.json() as OutfitCatalog;
  if (new URL(href).searchParams.get('experimental_layering') !== '1') return catalog;
  try {
    const layeredResponse = await fetcher('/data/experimental-layering.json');
    if (!layeredResponse.ok) return catalog;
    const manifest = await layeredResponse.json() as ExperimentalLayeringManifest;
    if (manifest.schemaVersion !== 1 || !manifest.outfits) return catalog;
    return { ...catalog, items: catalog.items.map(outfit => {
      const card = manifest.outfits[outfit.code];
      if (outfit.card.layers.length || card?.layout !== 'canvas' || !Array.isArray(card.layers) || card.layers.length < 4 || card.layers.length > 10) return outfit;
      return { ...outfit, card: { ...outfit.card, ...card } };
    }) };
  } catch { return catalog; }
}
