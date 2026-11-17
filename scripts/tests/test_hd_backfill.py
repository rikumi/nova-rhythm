import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'layering'))
from backfill_hd import backfill
from run_batch import digest


@unittest.skipUnless(all(importlib.util.find_spec(module) for module in ['numpy','scipy','PIL']),
                     'HD reconstruction tests require the optional local analysis dependencies')
class HDBackfillTests(unittest.TestCase):
    def test_visible_pixels_are_native_resolution_without_copying_foreground_into_hidden_background(self):
        import numpy as np
        from PIL import Image
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);folder=root/'input/0001';folder.mkdir(parents=True)
            original=np.zeros((96,128,3),dtype=np.uint8);original[:]=[20,30,100]
            yy,xx=np.indices((48,64))
            original[24:72,32:96]=np.stack([(xx%2)*180+50,(yy%2)*160+60,np.full_like(xx,40)],axis=2)
            Image.fromarray(original).save(folder/'original.png')
            background=Image.new('RGBA',(64,48),(20,30,100,255))
            foreground=Image.new('RGBA',(64,48));foreground.paste((170,80,40,255),(16,12,48,36))
            entries=[]
            for i,image in enumerate([background,foreground]):
                path=folder/f'layer-{i:02d}.png';image.save(path)
                entries.append({'file':path.name,'sha256':digest(path),'size':[64,48]})
            (folder/'result.json').write_text(json.dumps({'input_size':[64,48],'layers':entries}),encoding='utf8')
            original_hashes={path.name:digest(path) for path in folder.iterdir()}
            result=backfill('0001',root/'input',root/'output')
            out=root/'output/0001'
            with Image.open(out/'layer-01.png') as foreground:
                self.assertEqual(foreground.size,(128,96))
                self.assertEqual(foreground.getpixel((64,48))[:3],tuple(original[48,64]))
            with Image.open(out/'layer-00.png') as background:
                self.assertEqual(background.getpixel((64,48))[:3],(20,30,100))
            self.assertGreater(result['hd_backfill']['metrics']['psnr_db'],48)
            self.assertEqual(original_hashes,{path.name:digest(path) for path in folder.iterdir()})


if __name__=='__main__':unittest.main()
