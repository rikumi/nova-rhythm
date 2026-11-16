"""Create small JPEG sharing previews from the already exported covers."""
import argparse
import json
from pathlib import Path
from PIL import Image
from pipeline_paths import REPOSITORY, GAME, protect_output


def save_preview(image,target):
    image=image.convert('RGBA');image.thumbnail((640,640),Image.Resampling.LANCZOS)
    background=Image.new('RGBA',image.size,'#f3f6f8');background.alpha_composite(image)
    background.convert('RGB').save(target,'JPEG',quality=80,optimize=True)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--public-dir',type=Path,default=REPOSITORY/'public')
    args=parser.parse_args()
    public=protect_output(args.public_dir,GAME)
    outfits=json.loads((public/'data/outfits.json').read_text(encoding='utf8'))['items']
    total=0
    for outfit in outfits:
        folder=public/'art'/outfit['code']
        source=folder/'full.webp'
        with Image.open(source) as image:
            target=folder/'preview.jpg';save_preview(image,target)
        total+=target.stat().st_size
    print(f'Created {len(outfits)} JPEG previews; {total:,} bytes total.')


if __name__=='__main__':main()
