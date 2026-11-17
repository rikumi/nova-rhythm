import type { Outfit } from './types';

interface OutfitCatalog { schemaVersion: number; items: Outfit[]; }
export interface ExperimentalLayeringManifest {
  schemaVersion: number;
  enabled?: boolean;
  outfits: Record<string, Outfit['card']>;
}

export async function loadOutfits(_href: string, fetcher: typeof fetch = fetch): Promise<OutfitCatalog> {
  const response = await fetcher('/data/outfits.json');
  if (!response.ok) throw new Error('秘纹档案暂时无法读取');
  return await response.json() as OutfitCatalog;
}

export async function loadGeneratedCards(fetcher: typeof fetch = fetch): Promise<Record<string,Outfit['card']>> {
  try {
    const layeredResponse = await fetcher('/data/experimental-layering.json');
    if (!layeredResponse.ok) return {};
    const manifest = await layeredResponse.json() as ExperimentalLayeringManifest;
    if (manifest.schemaVersion !== 1 || manifest.enabled === false || !manifest.outfits) return {};
    return Object.fromEntries(Object.entries(manifest.outfits).filter(([,card])=>
      card?.layout === 'canvas' && Array.isArray(card.layers) && card.layers.length >= 2 && card.layers.length <= 10));
  } catch { return {}; }
}
