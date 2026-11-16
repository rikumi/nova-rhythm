"""Order deduplicated Cookie cues by variant and ascending runtime BPM state."""
import re


def cue_order(content):
    states = content.get('source_states', [])
    variants = {int(m[1] or 1) for state in states if state.get('group', '').lower() == 'system'
                and (m := re.fullmatch(r'cookie(\d*)', state.get('value', '').lower()))}
    cookie = {state.get('value', '').lower() for state in states if state.get('group', '').lower() == 'cookie'}
    bpms = sorted(int(m[1]) for value in cookie if (m := re.fullmatch(r'cookie_bpm(\d+)', value)))
    variant = min(variants, default=0)
    if not cookie or cookie <= {'none'}:
        return (0, -1, 0)
    if 'cookie_start' in cookie:
        return (variant, 0, 0)
    if bpms:
        return (variant, 1, bpms[0])
    if 'cookie_free' in cookie:
        return (variant, 2, 0)
    if 'cookie_end' in cookie:
        return (variant, 3, 0)
    return (variant, 4, 0)
