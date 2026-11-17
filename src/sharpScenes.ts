export interface SharpSceneInfo {
  input_size: [number, number]; camera_fov_y_degrees: number; focus_distance: number;
  depth_percentiles?: number[]; gaussian_count: number; scene_url: string; scene_format?: string;
}

export function sharpPreference(search: string, stored: unknown): boolean {
  return new URLSearchParams(search).get('sharp_3d') === '1' || stored === true;
}

let manifest: Promise<{outfits: Record<string, SharpSceneInfo>}> | undefined;
export async function loadSharpScene(code: string, local: boolean, signal: AbortSignal): Promise<SharpSceneInfo> {
  if (local) {
    const response = await fetch(`/__sharp-3d/${code}/scene.json`, {signal});
    if (!response.ok) throw new Error('未找到 SHARP 三维数据');
    return response.json();
  }
  manifest ??= fetch('/data/sharp-scenes.json').then(async response => {
    if (!response.ok) throw new Error('三维场景清单暂时无法读取');
    return response.json();
  }).catch(error => { manifest = undefined; throw error; });
  const info = (await manifest).outfits[code];
  if (!info || typeof info.scene_url !== 'string') throw new Error('此秘纹暂无三维场景');
  return info;
}

export async function sharpSceneAvailable(code: string, local: boolean, signal: AbortSignal): Promise<boolean> {
  const info = await loadSharpScene(code, local, signal);
  const response = await fetch(info.scene_url, {method: 'HEAD', signal});
  return response.ok;
}
