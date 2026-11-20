"""Compare cached official QQ playback with lossless game exports.

Chromaprint supplies compression-tolerant candidates; independent waveform
correlation verifies actual recordings before any name can be accepted.
"""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from scipy import signal
import imageio_ffmpeg
from pipeline_paths import REPOSITORY, GAME, protect_output

FRAME_SECONDS = 1365/11025


def load(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    temp.replace(path)


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def fingerprint(job, cli, cache, version):
    scope, identifier, path = job
    record_path = cache/(scope+'-'+identifier+'.json')
    source_hash = sha(path)
    if record_path.exists():
        prior = load(record_path)
        if prior.get('source_sha256') == source_hash and prior.get('tool_sha256') == version:
            return prior
    result = subprocess.run([str(cli), '-raw', '-json', '-length', '0', str(path)],
                            capture_output=True, text=True, encoding='utf8', errors='replace', timeout=120)
    if not result.stdout.strip():
        raise RuntimeError(f'No fingerprint for {identifier}: {result.stderr[:300]}')
    data = json.loads(result.stdout)
    record = {'id': identifier, 'scope': scope, 'source_sha256': source_hash, 'tool_sha256': version,
              'duration_seconds': data['duration'], 'fingerprint': data['fingerprint']}
    save(record_path, record)
    return record


def bands(value):
    value = int(value)
    for shift in [0, 8, 16, 24]:
        rotated = ((value >> shift) | (value << (32-shift))) & 0xffffffff if shift else value
        yield shift, rotated & 65535


def build_index(qq):
    index = defaultdict(list)
    for identifier, data in qq.items():
        for position, value in enumerate(data['fingerprint']):
            for band in bands(value):
                index[band].append((identifier, position))
    return {band: positions for band, positions in index.items() if len(positions) <= 250}


def fingerprint_candidates(local, qq, index, *, minimum_similarity=.86, limit=6):
    votes = Counter()
    fp = np.asarray(local['fingerprint'], dtype=np.uint32)
    for position in range(0, len(fp), 2):
        for band in bands(fp[position]):
            for identifier, q_position in index.get(band, []):
                votes[identifier, q_position-position] += 1
    grouped = defaultdict(list)
    for (identifier, offset), count in votes.most_common(200):
        if count < 8:
            break
        if len(grouped[identifier]) < 3:
            grouped[identifier].append((offset, count))
        if len(grouped) > 16:
            break
    candidates = []
    for identifier, offsets in grouped.items():
        qfp = np.asarray(qq[identifier]['fingerprint'], dtype=np.uint32)
        best = None
        minimum = min(160, max(32, int(min(len(fp), len(qfp))*.65)))
        for estimated, count in offsets:
            for offset in range(estimated-1, estimated+2):
                left, right = max(0, -offset), max(0, offset)
                length = min(len(fp)-left, len(qfp)-right)
                if length < minimum:
                    continue
                xor = np.bitwise_xor(fp[left:left+length], qfp[right:right+length])
                distance = np.bitwise_count(xor).mean()
                score = float(1-distance/32)
                candidate = {'qq_mid': identifier, 'fingerprint_similarity': round(score, 6),
                             'offset_frames': offset, 'offset_seconds': round(offset*FRAME_SECONDS, 6),
                             'overlap_seconds': round(length*FRAME_SECONDS, 3), 'votes': count,
                             'coverage_of_shorter': round(length/min(len(fp), len(qfp)), 4)}
                if best is None or score > best['fingerprint_similarity']:
                    best = candidate
        if best and best['fingerprint_similarity'] >= minimum_similarity:
            candidates.append(best)
    return sorted(candidates, key=lambda c: c['fingerprint_similarity'], reverse=True)[:limit]


def decode(path, start, length, rate=11025):
    result = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-ss', str(max(0, start)),
                             '-i', str(path), '-t', str(length), '-ac', '1', '-ar', str(rate), '-f', 'f32le', '-'],
                            capture_output=True, timeout=90)
    if result.returncode:
        raise RuntimeError(result.stderr.decode('utf8', errors='replace')[:500])
    return np.frombuffer(result.stdout, dtype='<f4').astype(np.float64)


def waveform_verify(candidate, local_path, qq_path, local_duration, qq_duration):
    """Check normalized waveform at independent positions, allowing codec delay."""
    offset = candidate['offset_seconds']
    local_start, qq_start = max(0, -offset), max(0, offset)
    overlap = min(local_duration-local_start, qq_duration-qq_start)
    length = min(18, max(5, overlap*.3))
    padding, rate = .65, 11025
    starts = sorted({max(1, overlap*.12), max(1, overlap*.52), max(1, overlap-length-2)})
    checks = []
    for relative in starts:
        if relative+length > overlap:
            continue
        left = decode(local_path, local_start+relative, length, rate)
        target_start = qq_start+relative
        right_start = max(0, target_start-padding)
        right = decode(qq_path, right_start, length+padding*2, rate)
        if len(left) < rate*3 or len(right) < len(left):
            continue
        left = left-left.mean()
        energy = np.dot(left, left)
        if energy < 1e-8:
            continue
        correlations = signal.correlate(right, left, mode='valid', method='fft')
        cumulative = np.concatenate([[0], np.cumsum(right*right)])
        rolling_energy = cumulative[len(left):]-cumulative[:-len(left)]
        normalized = np.abs(correlations)/np.sqrt(np.maximum(rolling_energy*energy, 1e-20))
        peak = int(np.argmax(normalized))
        checks.append({'local_seconds': round(local_start+relative, 3),
                       'qq_seconds': round(right_start+peak/rate, 3),
                       'window_seconds': round(len(left)/rate, 3),
                       'correlation': round(float(normalized[peak]), 6),
                       'verified_offset_seconds': round(right_start+peak/rate-local_start-relative, 6)})
    good = [c for c in checks if c['correlation'] >= .9]
    median = float(np.median([c['correlation'] for c in checks])) if checks else 0
    offsets = [c['verified_offset_seconds'] for c in good]
    stable = bool(offsets) and max(offsets)-min(offsets) <= .08
    verified = len(good) >= min(2, len(starts)) and median >= .92 and stable
    return dict(candidate, waveform_checks=checks, waveform_median=round(median, 6), verified=verified)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work-dir', type=Path, default=REPOSITORY/'.build/qqmusic')
    parser.add_argument('--fpcalc', type=Path, required=True)
    parser.add_argument('--audio-root', type=Path, default=REPOSITORY)
    parser.add_argument('--render-catalog', type=Path, default=REPOSITORY/'.build/import/catalog.json')
    parser.add_argument('--report', type=Path, default=REPOSITORY/'.build/qqmusic/matches.json')
    parser.add_argument('--jobs', type=int, default=4)
    args = parser.parse_args()
    work = protect_output(args.work_dir, GAME); protect_output(args.report, GAME)
    catalog = load(REPOSITORY/'references/qqmusic-catalog.json')
    downloads = load(work/'downloads.json')['downloads']
    contents = load(REPOSITORY/'references/analysis/content_groups.json')['contents']
    local_paths = {c['id']: args.audio_root/c['path'].lstrip('/') for c in contents}
    if args.render_catalog.exists():
        for row in load(args.render_catalog)['tracks']:
            path = args.render_catalog.parent/f'lossless/{row.get("render_key")}.flac'
            if row.get('status') == 'exported' and path.is_file():
                local_paths['audio-'+row['pcm_sha256']] = path
    qq_paths = {d['mid']: work/d['file'] for d in downloads if d['status'] in ['downloaded', 'cached']}
    jobs = [('project', identifier, path) for identifier, path in local_paths.items() if path.is_file()]
    jobs += [('qq', identifier, path) for identifier, path in qq_paths.items()]
    version = sha(args.fpcalc)
    fp, errors = {'project': {}, 'qq': {}}, []
    print(f'Fingerprinting {len(jobs)} files', flush=True)
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(fingerprint, job, args.fpcalc, work/'fingerprints', version): job for job in jobs}
        for i, future in enumerate(as_completed(futures), 1):
            try:
                row = future.result(); fp[row['scope']][row['id']] = row
            except Exception as exc:
                errors.append({'id': futures[future][1], 'error': str(exc)})
            if i % 50 == 0:
                print(f'Fingerprint {i}/{len(jobs)}', flush=True)
    index = build_index(fp['qq'])
    qq_songs = {s['mid']: s for s in catalog['songs']}
    matches, reviewed = [], []
    print('Matching fingerprints and verifying waveforms', flush=True)
    for i, (identifier, local) in enumerate(fp['project'].items(), 1):
        candidates = fingerprint_candidates(local, fp['qq'], index)
        verified = []
        for candidate in candidates[:3]:
            result = waveform_verify(candidate, local_paths[identifier], qq_paths[candidate['qq_mid']],
                                     local['duration_seconds'], fp['qq'][candidate['qq_mid']]['duration_seconds'])
            verified.append(result)
        accepted = [c for c in verified if c['verified']]
        titles = {qq_songs[c['qq_mid']]['title'] for c in accepted}
        row = {'audio_id': identifier, 'candidates': verified,
               'status': 'matched' if len(titles) == 1 else 'ambiguous' if titles else 'unmatched'}
        if row['status'] == 'matched':
            winner = max(accepted, key=lambda c: (c['waveform_median'], c['fingerprint_similarity']))
            song = qq_songs[winner['qq_mid']]
            row.update(qq_mid=song['mid'], official_title=song['title'], album=song['album'], url=song['url'], evidence=winner)
            matches.append(row)
        reviewed.append(row)
        if i % 25 == 0:
            print(f'Match {i}/{len(fp["project"])}: {len(matches)} verified', flush=True)
    report = {'schema_version': 1, 'artist': catalog['artist'], 'official_tracks': len(catalog['songs']),
              'downloaded_tracks': len(qq_paths), 'project_tracks': len(fp['project']),
              'method': {'fingerprint': 'Chromaprint 1.6.2 algorithm 2, full raw fingerprint',
                         'verification': 'Normalized waveform correlation on independent windows; median >= 0.92, at least two windows >= 0.9, stable offset within 80 ms',
                         'policy': 'A unique verified official title is required; no automatic name-only or duration-only matches.'},
              'matched': len(matches), 'matches': matches, 'results': reviewed, 'errors': errors}
    save(args.report, report)
    print(f'Verified {len(matches)}/{len(fp["project"])} project tracks against {len(qq_paths)} official tracks; {len(errors)} errors. Report: {args.report}', flush=True)


if __name__ == '__main__':
    main()
