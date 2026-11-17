"""Derive tiny fixed-width numeral faces from the bundled MiSans outlines."""
from pathlib import Path
from fontTools import subset
from fontTools.ttLib import TTFont
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.transformPen import TransformPen
from fontTools.misc.roundTools import otRound

ROOT=Path(__file__).resolve().parents[1]
for weight in ['Semibold','Bold']:
    source=ROOT/f'public/fonts/MiSans-{weight}.woff2'
    original=TTFont(source);font=TTFont(source);glyphs=original.getGlyphSet();cmap=font.getBestCmap()
    width=max(font['hmtx'].metrics[cmap[code]][0] for code in range(48,58))
    for code in range(48,58):
        name=cmap[code];advance,bearing=font['hmtx'].metrics[name];offset=otRound((width-advance)/2)
        pen=TTGlyphPen(glyphs);glyphs[name].draw(TransformPen(pen,(1,0,0,1,offset,0)))
        font['glyf'][name]=pen.glyph();font['hmtx'].metrics[name]=(width,bearing+offset)
    options=subset.Options();options.layout_features=['tnum']
    selection=subset.Subsetter(options);selection.populate(unicodes=range(48,58));selection.subset(font)
    for record in font['name'].names:
        replacement={1:'Nova Rhythm Digits',4:f'Nova Rhythm Digits {weight}',6:f'NovaRhythmDigits-{weight}',16:'Nova Rhythm Digits'}
        if record.nameID in replacement:record.string=replacement[record.nameID].encode(record.getEncoding())
    target=ROOT/f'public/fonts/NovaRhythmDigits-{weight}.woff2';font.save(target)
    print(target.name,target.stat().st_size,'bytes, advance',width)
