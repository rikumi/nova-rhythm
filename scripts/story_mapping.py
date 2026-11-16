"""Human-editable story library mapping; technical metadata remains generated."""
import copy
from pathlib import PurePosixPath
import re


def ordered_groups(groups):
    """Dated groups retain date order; explicit anchors place permanent modes."""
    by_id = {g['id']: g for g in groups}
    children = {}
    for group in groups:
        if group.get('before_group') in by_id:
            children.setdefault(group['before_group'], []).append(group)
    result, seen, visiting = [], set(), set()
    def emit(group):
        if group['id'] in visiting:
            raise ValueError('Cyclic before_group ordering')
        if group['id'] in seen:
            return
        visiting.add(group['id'])
        for child in children.get(group['id'], []):
            emit(child)
        visiting.remove(group['id']); seen.add(group['id']); result.append(group)
    for group in sorted(groups, key=lambda g: g.get('date', ''), reverse=True):
        if group.get('before_group') not in by_id:
            emit(group)
    for group in groups:
        emit(group)
    return result


def to_mapping(library, previous=None):
    tracks = {t['id']: t for t in library['tracks']}
    result = {'schema_version': 1, 'groups': [
        {'id': g['id'], 'name': g['name'], 'date': g.get('date', ''),
         'description': g.get('description', ''),
         'outfit_references': copy.deepcopy(g.get('outfit_references', [])),
         'tracks': [{'name': t['title'], 'file': t['path'],
                     'description': t.get('description', '')}
                    for t in (tracks[identifier] for identifier in g['track_ids'])]}
        for g in library['groups']]}
    if previous:
        old_groups = {g['id']: g for g in previous['groups']}
        old_tracks = {t['file']: t for g in previous['groups'] for t in g.get('tracks', [])}
        for group in result['groups']:
            group['tracks'] = [{**copy.deepcopy(old_tracks.get(t['file'], {})), **t} for t in group['tracks']]
            old = old_groups.get(group['id'], {})
            for key, value in old.items():
                if key not in group:
                    group[key] = copy.deepcopy(value)
    return result


def apply_mapping(mapping, metadata):
    if mapping.get('schema_version') != 1 or not isinstance(mapping.get('groups'), list):
        raise ValueError('story-melodies.json: expected schema_version: 1 and groups array')
    by_file = {t['path']: t for t in metadata.get('tracks', [])}
    groups, tracks, group_ids, track_ids, files = [], [], set(), set(), set()
    for raw in mapping['groups']:
        identifier, name, date = raw.get('id'), raw.get('name'), raw.get('date') or ''
        if not identifier or not name or identifier in group_ids:
            raise ValueError(f'Invalid or duplicate story group: {identifier}')
        if date and not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:T.*)?', date):
            raise ValueError(f'Invalid story date: {date}; use YYYY-MM-DD or ISO 8601')
        group_ids.add(identifier)
        group = {'id': identifier, 'name': name, 'date': date, 'track_ids': [],
                 'outfit_references': copy.deepcopy(raw.get('outfit_references', []))}
        if raw.get('description'):
            group['description'] = raw['description']
        if raw.get('before_group'):
            group['before_group'] = raw['before_group']
        if 'minimum_duration_seconds' in raw:
            minimum = raw['minimum_duration_seconds']
            if not isinstance(minimum, (int, float)) or minimum < 0:
                raise ValueError('minimum_duration_seconds must be nonnegative')
            group['minimum_duration_seconds'] = minimum
        for entry in raw.get('tracks', []):
            file = entry.get('file', '')
            if not file.startswith(('/', 'https://')) or file.startswith('//') or '..' in file.split('/'):
                raise ValueError(f'Invalid story audio file: {file}')
            old = by_file.get(file, {})
            track_id = entry.get('id') or old.get('id') or file
            if track_id in track_ids or file in files:
                raise ValueError(f'Story audio listed more than once: {file}')
            track_ids.add(track_id); files.add(file)
            title = entry.get('name') or PurePosixPath(file).stem
            track = {'sample_rate': 44100, 'channels': 2, 'number_of_samples': 0,
                     'duration_seconds': 0, 'loop': None, 'source_title': title,
                     'uses': [], 'aliases': [], **copy.deepcopy(old),
                     'id': track_id, 'title': title, 'path': file, 'group_id': identifier}
            if entry.get('description'):
                track['description'] = entry['description']
            else:
                track.pop('description', None)
            tracks.append(track); group['track_ids'].append(track_id)
        groups.append(group)
    groups = ordered_groups(groups)
    # Preserve technical catalog order, independently of curated display ordering.
    old_order = {t['id']: index for index, t in enumerate(metadata.get('tracks', []))}
    tracks.sort(key=lambda t: old_order.get(t['id'], len(old_order)))
    return {'schema_version': 2, 'groups': groups, 'tracks': tracks}
