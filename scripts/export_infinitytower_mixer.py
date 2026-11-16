"""Export fixed and eight selectable music segments without writing game inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import wave
import numpy as np
from pipeline_paths import REPOSITORY, GAME, CLI, protect_output

RATE = 44100
INTRO = 75600
SECTIONS = [1209600, 604800, 1209600, 1814400, 604800]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-dir', type=Path, default=GAME)
    parser.add_argument('--output', type=Path, default=REPOSITORY/'public')
    parser.add_argument('--work-dir', type=Path, default=REPOSITORY/'.build/infinitytower-mixer')
    args = parser.parse_args()
    import imageio_ffmpeg
    output, work = protect_output(args.output, args.game_dir), protect_output(args.work_dir, args.game_dir)
    work.mkdir(parents=True, exist_ok=True)
    target = output/'audio/infinitytower'; target.mkdir(parents=True, exist_ok=True)
    wem = args.game_dir/'xtlr_Data/StreamingAssets/InstallResource/txtp/wem'
    ids = [623406877, 147622662, 840557293, 690354636, 762396951, 573861789, 177005291]
    decoded = {}; source_hashes = {}
    for identifier in ids:
        path = wem/f'{identifier}.wem'
        source_hashes[str(identifier)] = hashlib.sha256(path.read_bytes()).hexdigest()
        wav = work/f'{identifier}.wav'
        subprocess.run([str(CLI), '-i', '-o', str(wav), str(path)], check=True, capture_output=True)
        with wave.open(str(wav)) as source:
            assert source.getframerate() == RATE and source.getnchannels() == 2 and source.getsampwidth() == 2
            decoded[identifier] = np.frombuffer(source.readframes(source.getnframes()), dtype='<i2').reshape(-1,2).astype(np.float64)/32768
    def piece(identifier, begin, length, db=0):
        data = decoded[identifier][begin:begin+length]*10**(db/20)
        return np.pad(data, ((0,max(0,length-len(data))),(0,0)))
    # Keep only the fixed intro and fixed third section in the compact main stem.
    main_data = np.concatenate([piece(623406877,0,INTRO),piece(840557293,0,SECTIONS[2],-3)])
    stems = [('main',main_data)]
    stems += [('part-1-a',piece(623406877,1890000,SECTIONS[0])),('part-1-b',piece(623406877,INTRO,SECTIONS[0]))]
    second_a=piece(623406877,1285200,SECTIONS[1],-2);second_b=piece(147622662,0,SECTIONS[1],-3)
    stems += [('part-2-a',second_a),('part-2-b',second_b)]
    stems += [('part-3-a',np.concatenate([piece(690354636,0,604800,-2),piece(762396951,0,1209600,-3)])),
              ('part-3-b',np.concatenate([piece(573861789,0,604800,-2),piece(177005291,0,1209600,-3)]))]
    stems += [('part-4-a',second_a),('part-4-b',second_b)]
    for name,data in stems:
        wav = work/(name+'.wav')
        with wave.open(str(wav),'wb') as dest:
            dest.setnchannels(2);dest.setsampwidth(2);dest.setframerate(RATE)
            dest.writeframes(np.rint(np.clip(data,-1,1-1/32768)*32768).astype('<i2').tobytes())
        subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-v','error','-y','-i',str(wav),'-c:a','libopus','-b:a','160k','-ar','48000',str(target/(name+'.opus'))],check=True)
    starts = np.cumsum([INTRO]+SECTIONS[:-1]).tolist()
    def cue(start,frames,offset=0):return {'start':start/RATE,'duration':frames/RATE,'offset':offset/RATE}
    streams = [{'id':'main','path':'/audio/infinitytower/main.opus','cues':[cue(0,INTRO),cue(starts[2],SECTIONS[2],INTRO)]}]
    for row,section in enumerate([0,1,3,4]):
        for option in range(2):
            name=f'part-{row+1}-'+('a' if option==0 else 'b')
            streams.append({'id':name,'row':row,'option':option,'path':f'/audio/infinitytower/{name}.opus','cues':[cue(starts[section],SECTIONS[section])]})
    catalog=json.loads((REPOSITORY/'references/analysis/catalog.json').read_text(encoding='utf8'))
    combinations={'audio-'+r['pcm_sha256']:[n-1 for n in r['random_choices']] for r in catalog['tracks'] if r.get('parent_id')=='install-082d09f35a2d' and r.get('random_choices')}
    definition={'schema_version':1,'track_id':'audio-172ce969c65aff62f5f9a75c3f96a651a5db454987aac662f451c65ea036284c',
                'duration':(INTRO+sum(SECTIONS))/RATE,'loop_start':INTRO/RATE,'crossfade_seconds':0.35,
                'streams':streams,'combinations':combinations,'source_sha256':source_hashes,
                'notes':'Four independent sequential segment selectors, not isolated instruments. Original -2/-3 dB recipe gains retained. Musical grid uses 44100 Hz sample boundaries; short Vorbis tails padded by at most 300 samples to maintain synchronized loop timing.'}
    (output/'data').mkdir(parents=True, exist_ok=True)
    (output/'data/infinitytower-mixer.json').write_text(json.dumps(definition,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(f'Exported {len(streams)} compact stems; musical loop {sum(SECTIONS)/RATE:.6f}s; game files unchanged.')


if __name__=='__main__':main()
