import assert from 'node:assert/strict';
import test from 'node:test';
import {downloadScene} from '../../src/sharpTransport.ts';

const bytes=new TextEncoder().encode('a complete scene payload');
const options=fetcher=>({fetcher,signal:new AbortController().signal,total:bytes.length,progress:()=>{},retryDelayMs:0});
function brokenPrefix(count,signal,stall=false){
  return new Response(new ReadableStream({
    start(controller){
      controller.enqueue(bytes.slice(0,count));
      if(stall)signal.addEventListener('abort',()=>controller.error(signal.reason),{once:true});
    },
    pull(controller){if(!stall)controller.error(new TypeError('connection interrupted'));},
  }));
}

test('interrupted downloads resume from the received offset without duplicating bytes',async()=>{
  const headers=[];
  const result=await downloadScene('/scene',options(async(_url,init)=>{
    headers.push(init.headers?.Range);
    if(headers.length===1)return brokenPrefix(7,init.signal);
    return new Response(bytes.slice(7),{status:206,headers:{'Content-Range':`bytes 7-${bytes.length-1}/${bytes.length}`}});
  }));
  assert.deepEqual(headers,[undefined,'bytes=7-']);
  assert.deepEqual(new Uint8Array(await result.arrayBuffer()),bytes);
});

test('a server ignoring Range restarts safely instead of concatenating duplicate prefixes',async()=>{
  let calls=0;
  const result=await downloadScene('/scene',options(async(_url,init)=>++calls===1?brokenPrefix(7,init.signal):new Response(bytes)));
  assert.equal(calls,2);assert.deepEqual(new Uint8Array(await result.arrayBuffer()),bytes);
});

test('stalled transfer retries its partial body, while continuous slow progress has no total timeout',async()=>{
  let calls=0;
  const resumed=await downloadScene('/scene',{...options(async(_url,init)=>{
    calls++;return calls===1?brokenPrefix(7,init.signal,true):new Response(bytes.slice(7),{status:206});
  }),idleMs:20});
  assert.equal(calls,2);assert.equal(resumed.size,bytes.length);
  calls=0;
  const slow=await downloadScene('/slow',{...options(async()=>{
    calls++;let offset=0;
    return new Response(new ReadableStream({start(controller){
      const timer=setInterval(()=>{
        controller.enqueue(bytes.slice(offset,offset+4));offset+=4;
        if(offset>=bytes.length){clearInterval(timer);controller.close();}
      },30);
    }}));
  }),idleMs:100});
  assert.equal(calls,1);assert.equal(slow.size,bytes.length);
});

test('missing files fail immediately and user cancellation does not trigger retries',async()=>{
  let calls=0;
  await assert.rejects(downloadScene('/missing',options(async()=>{calls++;return new Response('',{status:404});})),/404/);
  assert.equal(calls,1);
  const controller=new AbortController();calls=0;
  const pending=downloadScene('/cancel',{...options(async(_url,init)=>{calls++;return brokenPrefix(7,init.signal,true);}),signal:controller.signal});
  setTimeout(()=>controller.abort(),10);
  await assert.rejects(pending,{name:'AbortError'});assert.equal(calls,1);
});
