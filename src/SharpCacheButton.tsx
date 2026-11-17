import { useSyncExternalStore } from 'react';
import { Check } from 'lucide-react';
import { modelCacheState, setModelCached, subscribeModelCache } from './sharpModelCache';

export function SharpCacheButton({code,onError}:{code:string;onError:(message:string)=>void}) {
  const state=useSyncExternalStore(subscribeModelCache,()=>modelCacheState(code));
  if(!state.downloaded)return null;
  return <button className="save-card model-cache-control" role="checkbox" aria-label="缓存" aria-checked={state.cached} aria-busy={state.pending} disabled={state.pending} onClick={()=>{
    void setModelCached(code,!state.cached).catch(()=>onError('无法更新模型缓存，请检查本地存储空间'));
  }}><span className="model-cache-check" aria-hidden="true">{state.cached&&<Check size={11}/>}</span>缓存</button>;
}
