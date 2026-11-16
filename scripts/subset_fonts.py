from pathlib import Path
from fontTools import subset
from pipeline_paths import ROOT
text=''.join(p.read_text(encoding='utf8') for p in (ROOT/'public/data').glob('*.json'))+''.join(p.read_text(encoding='utf8') for p in (ROOT/'src').glob('*') if p.suffix in ['.ts','.tsx'])
for name in ['MiSans-Semibold','MiSans-Bold']:
 font=subset.load_font(str(ROOT/'assets/fonts'/(name+'.ttf')),subset.Options())
 options=subset.Options();options.flavor='woff2';options.desubroutinize=True
 sub=subset.Subsetter(options=options);sub.populate(text=text);sub.subset(font)
 target=ROOT/'public/fonts'/(name+'.woff2');target.parent.mkdir(parents=True,exist_ok=True);font.flavor='woff2';font.save(str(target));print(target.name,target.stat().st_size)
