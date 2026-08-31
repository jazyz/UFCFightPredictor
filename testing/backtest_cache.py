# Versioned cache directories for the walk-forward backtests. Cached per-retrain
# predictions are only valid for one (training code, params, data) vintage, so the
# cache lives under a tag hashed from those inputs: any change to them lands in a
# fresh directory and old caches become inert instead of silently mixed in.
import hashlib
import json
import os

# Full content hash of all three, including the ~14MB CSV (streamed, tens of ms):
# unlike size+mtime it neither invalidates on mtime-only rewrites nor collides on
# a same-size rewrite.
_INPUTS = [
    os.path.join('testing', 'ml_alpha_testing.py'),
    os.path.join('data', 'best_params.json'),
    os.path.join('data', 'detailed_fights.csv'),
]

def _sha256_file(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for chunk in iter(lambda: f.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()

def cache_dir(base_dir):
    manifest = {path: {'sha256': _sha256_file(path), 'size': os.path.getsize(path)}
                for path in _INPUTS}
    tag = hashlib.sha256('\n'.join(manifest[p]['sha256'] for p in _INPUTS).encode()).hexdigest()[:12]
    d = os.path.join(base_dir, tag)
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, 'manifest.json'), 'w') as f:
        json.dump(manifest, f, indent=2)
    return d
