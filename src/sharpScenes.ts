export interface SharpSceneInfo {
  input_size: [number, number]; camera_fov_y_degrees: number; focus_distance: number;
  depth_percentiles?: number[]; gaussian_count: number; scene_url: string; scene_format?: string;
  compressed_bytes?: number;
  scene_bytes?: number; scene_sha256?: string;
}

let manifest: Promise<{outfits: Record<string, SharpSceneInfo>}> | undefined;
export function loadSharpManifest(): Promise<{outfits: Record<string, SharpSceneInfo>}> {
  return manifest ??= fetch('/data/sharp-scenes.json').then(async response => {
    if (!response.ok) throw new Error('三维场景清单暂时无法读取');
    const data = await response.json();
    return {outfits: Object.fromEntries(Object.entries(data.outfits || {}).filter(([,value]) =>
      typeof (value as SharpSceneInfo)?.scene_url === 'string')) as Record<string, SharpSceneInfo>};
  }).catch(error => { manifest = undefined; throw error; });
}
export async function loadSharpScene(code: string, local: boolean, signal: AbortSignal): Promise<SharpSceneInfo> {
  if (local) {
    const response = await fetch(`/__sharp-3d/${code}/scene.json`, {signal});
    if (!response.ok) throw new Error('未找到 SHARP 三维数据');
    return response.json();
  }
  const info = (await loadSharpManifest()).outfits[code];
  if (!info || typeof info.scene_url !== 'string') throw new Error('此秘纹暂无三维场景');
  return info;
}
