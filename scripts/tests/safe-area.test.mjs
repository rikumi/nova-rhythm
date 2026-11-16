import assert from 'node:assert/strict';
import test from 'node:test';
import { androidBottomInset } from '../../src/safeArea.ts';
const metrics={installed:true,android:true,native:0,maximum:0,viewportHeight:844,visualHeight:844,visualTop:0,scale:1,screenY:0,screenHeight:844,availableTop:0,availableHeight:844,keyboardOpen:false};
test('installed Android gets a conservative guard when all geometry reports zero',()=>{
  assert.deepEqual(androidBottomInset(metrics),{bottom:32,source:'android-pwa-fallback'});
  assert.equal(androidBottomInset({...metrics,installed:false}).bottom,0);
  assert.equal(androidBottomInset({...metrics,android:false}).bottom,0);
});
test('native and maximum insets take precedence over estimated geometry',()=>{
  assert.deepEqual(androidBottomInset({...metrics,native:24}),{bottom:24,source:'native-inset'});
  assert.deepEqual(androidBottomInset({...metrics,maximum:48}),{bottom:48,source:'maximum-inset'});
  assert.equal(androidBottomInset({...metrics,native:34,maximum:24}).bottom,34);
});
test('uses visible viewport or screen-available overlap without treating keyboard or zoom as insets',()=>{
  assert.deepEqual(androidBottomInset({...metrics,visualHeight:816}),{bottom:28,source:'visual-viewport'});
  assert.deepEqual(androidBottomInset({...metrics,availableHeight:796}),{bottom:48,source:'screen-available'});
  assert.equal(androidBottomInset({...metrics,visualHeight:500,keyboardOpen:true}).bottom,0);
  assert.equal(androidBottomInset({...metrics,visualHeight:816,scale:2}).source,'android-pwa-fallback');
  assert.equal(androidBottomInset({...metrics,visualHeight:400}).bottom,32);
});
