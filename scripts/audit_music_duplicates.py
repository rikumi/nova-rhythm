"""Review near-duplicate music using original lossless exports, never website Opus.

The report is incremental (source/tool hashes fingerprint caches), and read-only
by default. Related arrangements or tempo variants must pass waveform checks.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

from match_qqmusic import (build_index, fingerprint, fingerprint_candidates,
                           load, save, sha, waveform_verify)
from pipeline_paths import REPOSITORY, protect_output
from story_mapping import apply_mapping


def prepare():
    mapping = load(REPOSITORY/'public/data/story-melodies.json')
    library = apply_mapping(mapping, load(REPOSITORY/'public/data/library.json'))
    contents = {c['id']: c for c in load(REPOSITORY/'references/analysis/content_groups.json')['contents']}
    groups = {g['id']: g for g in mapping['groups']}
    order = {t['audio_id']: t for g in load(REPOSITORY/'references/story-music-order.json')['groups'] for t in g['tracks']}
    mixer = load(REPOSITORY/'public/data/infinitytower-mixer.json')
    protected = set(mixer['combinations']) | {mixer['track_id']}
    canonical = {row['id'] for row in load(REPOSITORY/'references/music-duplicate-overrides.json')['canonical']}
    tracks = {}
    for index, track in enumerate(library['tracks']):
        if track['id'] in protected:
            continue
        group = groups[track['group_id']]
        first = order.get(track['id'], {}).get('first_appearance') or {}
        date = group.get('date') or (first.get('sort_key') or ['2025-10-20'])[0]
        tracks[track['id']] = {**track, 'scope': 'story', 'collection': group['name'],
                               'priority': [.5 if track['id'] in canonical else 1, date[:10], first.get('chapter_order', 999999), first.get('call_line', 999999), index]}
    for outfit in load(REPOSITORY/'public/data/outfits.json')['items']:
        for index, track in enumerate(outfit['music']):
            tracks[track['id']] = {**track, 'scope': 'outfit', 'collection': outfit['name'],
                                   'priority': [0, outfit['activity'].get('date', ''), index, outfit['id'], 0]}
    for identifier, track in tracks.items():
        source = contents[identifier]
        path = REPOSITORY/source['path'].lstrip('/')
        if not path.is_file() or path.suffix.lower() != '.flac':
            raise FileNotFoundError(f'Missing original lossless music: {path}')
        track['lossless_path'] = str(path)
        track['source_duration'] = source['duration_seconds']
        track['current_duration_differs'] = abs(track['duration_seconds']-source['duration_seconds']) > .5
    return mapping, tracks


def assess(result, left_duration, right_duration, loser_is_left):
    checks = result['waveform_checks']
    stable = len(checks) >= 3 and max(c['verified_offset_seconds'] for c in checks)-min(c['verified_offset_seconds'] for c in checks) <= .08
    verified = stable and result['waveform_median'] >= .88 and min(c['correlation'] for c in checks) >= .80
    offset = result['offset_seconds']
    overlap = max(0, min(left_duration-max(0,-offset), right_duration-max(0,offset)))
    coverage = overlap/(left_duration if loser_is_left else right_duration)
    return {'verified': verified, 'stable_alignment': stable, 'removed_track_coverage': round(coverage, 6),
            'eligible': verified and coverage >= .85}


def brief(track):
    return {k: track[k] for k in ['id', 'scope', 'collection', 'title', 'path', 'priority', 'source_duration', 'duration_seconds', 'current_duration_differs', 'lossless_sha256']}


def protected_variant_pair(left, right):
    # These entries are intentional tempo/free-play choices in the game, even
    # when a free-play render contains the corresponding tempo segment.
    return left.get('group_id') == right.get('group_id') == 'mode-甜心梦工坊'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=REPOSITORY/'references/music-duplicate-review.json')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--candidate-threshold', type=float, default=.82)
    args = parser.parse_args()
    protect_output(args.report)
    previous = load(args.report) if args.report.exists() else {}
    mapping, tracks = prepare()
    mapping_path = REPOSITORY/'public/data/story-melodies.json'
    mapping_hash = sha(mapping_path)
    cli = REPOSITORY/'tools/chromaprint/chromaprint-fpcalc-1.6.2-windows-x86_64/fpcalc.exe'
    version = sha(cli)
    def fp(identifier):
        return fingerprint(('project', identifier, Path(tracks[identifier]['lossless_path'])), cli,
                           REPOSITORY/'.build/qqmusic/fingerprints', version)
    with ThreadPoolExecutor(max_workers=4) as pool:
        fingerprints = dict(zip(tracks, pool.map(fp, tracks)))
    for identifier, data in fingerprints.items():
        tracks[identifier]['lossless_sha256'] = data['source_sha256']
    index = build_index(fingerprints)
    reviewed, seen = [], set()
    stories = [identifier for identifier, track in tracks.items() if track['scope'] == 'story']
    for number, identifier in enumerate(stories, 1):
        candidates = fingerprint_candidates(fingerprints[identifier], fingerprints, index, minimum_similarity=args.candidate_threshold, limit=24)
        for candidate in candidates:
            other_id = candidate['qq_mid']
            pair = tuple(sorted([identifier, other_id]))
            if identifier == other_id or pair in seen:
                continue
            seen.add(pair)
            left, right = tracks[identifier], tracks[other_id]
            winner, loser = sorted([left, right], key=lambda t: t['priority'])
            result = waveform_verify(candidate, left['lossless_path'], right['lossless_path'], left['source_duration'], right['source_duration'])
            result.update(assess(result, left['source_duration'], right['source_duration'], loser is left))
            protected = protected_variant_pair(left, right)
            eligible = result['eligible'] and loser['scope'] == 'story' and not protected and not (loser['current_duration_differs'] or winner['current_duration_differs'])
            reviewed.append({'keep': brief(winner), 'remove': brief(loser), 'waveform_source_ids': [identifier, other_id], 'evidence': result, 'protected_playback_variants': protected, 'eligible': eligible})
            print(f'{number}/{len(stories)}: {loser["title"]} -> {winner["collection"]} / {winner["title"]}: median={result["waveform_median"]} eligible={eligible}', flush=True)
        if number % 25 == 0:
            print(f'Compared {number}/{len(stories)} story tracks; {len(reviewed)} candidate pairs', flush=True)
    # Retain evidence for already removed tracks when auditing an updated mapping.
    pairs = {tuple(sorted([r['keep']['id'], r['remove']['id']])): r for r in previous.get('results', [])}
    pairs.update({tuple(sorted([r['keep']['id'], r['remove']['id']])): r for r in reviewed})
    report = {'schema_version': 1, 'mapping_sha256_before': mapping_hash,
              'method': {'source': 'original lossless game FLAC only', 'fingerprint_minimum': args.candidate_threshold,
                         'waveform_median_minimum': .88, 'every_window_minimum': .80, 'minimum_windows': 3,
                         'offset_spread_max_seconds': .08, 'removed_track_minimum_coverage': .85,
                         'recording_policy': 'User confirmed: merge only substantially identical recordings; retain different arrangements/mixes and partial shared sections',
                         'priority': 'Outfit first, then explicit canonical overrides, then earlier story release date / chapter / command order; protect mixer, cookie tempo/free-play variants and changed full official versions'},
              'audited_tracks': len(tracks), 'audited_story_tracks': len(stories),
              'results': list(pairs.values()), 'removed': previous.get('removed', []), 'newly_removed': []}
    if args.apply:
        if sha(mapping_path) != mapping_hash:
            raise RuntimeError('Mapping changed during analysis; refusing to overwrite user edits')
        # Resolve directed chains; never remove a surviving earlier track merely
        # because it also resembles a later track. Every removed track has direct evidence.
        removals = {row['remove']['id'] for row in reviewed if row['eligible']}
        by_file = {t['path']: t for t in tracks.values()}
        for group in mapping['groups']:
            kept = []
            for entry in group.get('tracks', []):
                track = by_file.get(entry['file'])
                if track and track['id'] in removals:
                    report['newly_removed'].append({'group_id': group['id'], 'group_name': group['name'], 'entry': entry, 'audio_id': track['id']})
                else:
                    kept.append(entry)
            group['tracks'] = kept
        save(mapping_path, mapping)
    removed_by_file = {r['entry']['file']: r for r in report['removed']+report['newly_removed']}
    report['removed'] = list(removed_by_file.values())
    save(args.report, report)
    print(f'Audited {len(tracks)} tracks; {len(reviewed)} candidate pairs; {sum(r["eligible"] for r in reviewed)} verified pairs; {len(report["newly_removed"])} newly removed; {len(report["removed"])} historical removals', flush=True)


if __name__ == '__main__':
    main()
