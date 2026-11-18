"""Recover stripped Unity component schemas from identical local serialized types.

Only in-memory objects are read. Neither the target nor donor bundles are changed.
"""
from pathlib import Path

import UnityPy


def type_key(serialized_type):
    return (serialized_type.class_id, serialized_type.script_id, serialized_type.old_type_hash)


class TypeTreeCache:
    def __init__(self, candidates):
        self.candidates = iter(candidates)
        self.nodes = {}
        self.sources = {}

    def register(self, environment, source):
        for obj in environment.objects:
            kind = obj.serialized_type
            if kind and kind.node is not None:
                key = type_key(kind)
                self.nodes.setdefault(key, kind.node)
                self.sources.setdefault(key, str(source))

    def read(self, obj):
        kind = obj.serialized_type
        if kind.node is not None:
            return obj.read_typetree()
        key = type_key(kind)
        if key not in self.nodes:
            for path in self.candidates:
                self.register(UnityPy.load(str(path)), path)
                if key in self.nodes:
                    break
        if key not in self.nodes:
            # Preserve UnityPy's validation error instead of guessing field offsets.
            return obj.read_typetree()
        return obj.read_typetree(nodes=self.nodes[key], check_read=True)


_caches = {}


def component_reader(bundle, environment):
    directory = Path(bundle).resolve().parent
    if directory not in _caches:
        directories = [directory]
        # Version bundles may strip schemas that are still present in install bundles.
        for parent in directory.parents:
            if parent.name in ('Persistent_Store', 'xtlr_Data'):
                game = parent.parent
                directories += [game/'xtlr_Data/StreamingAssets/InstallResource',
                                game/'Persistent_Store/AssetBundles']
                break
        candidates = []
        for folder in dict.fromkeys(directories):
            candidates += sorted(folder.glob('disc_*.unity3d'), reverse=True)
        _caches[directory] = TypeTreeCache(candidates)
    cache = _caches[directory]
    cache.register(environment, bundle)
    return cache.read
