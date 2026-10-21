"""Presentation for the free creation storefront; no runtime data is published."""
import hashlib
import struct
from pathlib import Path
from .contracts import require
from .packages import check_url, download

MEDIA = Path(__file__).parent / 'web/media'
PROJECT = 'https://github.com/josethevrtech/magicshelf'
BUILTINS = {
    'org.magicshelf.android-phone': {
        'category': 'Utilities', 'author': 'josethevrtech',
        'tagline': 'A little Android. A lot of possibility.',
        'description': 'Your own Android phone, right beside you in VR.',
        'about': 'Keep your Android apps within reach. Pick up the phone, move it around your space, or return it to the shelf. Its screen supports controller taps, swipes, typing and brightness controls. Turn it off to pause Android and its audio; turn it on to pick up where you left off.',
        'screenshots': [{'asset': 'phone.png', 'caption': 'The original graphite phone, rendered by MagicShelf.'}, {'asset': 'phone-settings.png', 'caption': 'On-device controls for brightness, size and placement.'}],
        'links': [{'label': 'Android Phone on GitHub', 'url': 'https://github.com/josethevrtech/magicshelf-android-phone'}, {'label': 'MagicShelf framework', 'url': PROJECT}],
        'credits': [{'name': 'josethevrtech', 'role': 'Creation, original phone model and integration', 'url': 'https://github.com/josethevrtech', 'license': 'Original procedural phone geometry.'}],
    },
    'org.magicshelf.digital-partner': {
        'category': 'Companions', 'author': 'josethevrtech',
        'tagline': 'A digital companion, now in your world.',
        'description': 'Give your Digital Partner a place on your shelf.',
        'about': 'A live Digital Partner game inside the Courage smartphone Digivice. Pick it up, interact with your pet, and keep it nearby in VR. The grab bar supports depth adjustment, and a shake sends it home. Off pauses the game and its audio while preserving your session.',
        'screenshots': [{'asset': 'digivice.png', 'caption': 'Digital Partner in Jojogape’s Courage Digivice model.'}, {'asset': 'digivice-back.png', 'caption': 'The Courage case and crest, viewed from the back.'}],
        'links': [{'label': 'Digivice on GitHub', 'url': 'https://github.com/josethevrtech/magicshelf-digivice'}, {'label': 'MagicShelf framework', 'url': PROJECT}, {'label': 'Digital Partner game', 'url': 'https://aludeku.itch.io/digital-partner-digimon'}],
        'credits': [
            {'name': 'Jojogape', 'role': 'Smartphone Digivice 3D model', 'url': 'https://x.com/jojogape', 'license': 'Artist-provided personal-use model; no use for profit.'},
            {'name': 'Aludeku', 'role': 'Digital Partner game', 'url': 'https://aludeku.itch.io/digital-partner-digimon', 'support_url': 'https://aludeku.itch.io/digital-partner-digimon', 'license': 'Game, characters and artwork retain their original rights.'},
            {'name': 'boardernerd', 'role': 'Original Season 1 Digivice used for the legacy icon', 'url': 'https://www.thingiverse.com/thing:2695824', 'license': 'Creative Commons Attribution.'},
        ],
    },
}

def image_key(url):
    return hashlib.sha256(url.encode()).hexdigest() + '.png'

def valid_png(path):
    """Bound image dimensions before either frontend decodes a catalog preview."""
    with path.open('rb') as f:
        header = f.read(24)
    require(len(header) == 24 and header[:8] == b'\x89PNG\r\n\x1a\n' and header[12:16] == b'IHDR', 'Screenshot must be a PNG')
    w, h = struct.unpack('>II', header[16:24])
    require(0 < w <= 4096 and 0 < h <= 4096 and w * h <= 8_000_000, 'Screenshot is too large')

def cache_images(items, root):
    cache = root / 'previews'
    cache.mkdir(parents=True, exist_ok=True)
    for item in items:
        for picture in item.get('screenshots', []):
            target = cache / image_key(picture['url'])
            if target.exists():
                continue
            temporary = target.with_suffix('.part')
            try:
                check_url(picture['url'])
                download(picture['url'], temporary, 6 * 1024 * 1024)
                valid_png(temporary)
                temporary.replace(target)
            except Exception:
                # A missing preview must never block installing a creation.
                temporary.unlink(missing_ok=True)

def decorate(meta, root):
    builtin = BUILTINS.get(meta['id'], {}) if meta.get('adapter') else {}
    value = {**meta, **builtin}
    value['price_label'] = 'Free'
    value.setdefault('category', 'Creations')
    value.setdefault('about', value['description'])
    value.setdefault('links', [])
    value.setdefault('credits', [])
    pictures = []
    for picture in value.get('screenshots', []):
        # Only our built-in metadata may reference bundled filesystem assets.
        # Catalog screenshots always go through the bounded download cache.
        asset = picture.get('asset') if builtin else None
        path = MEDIA / asset if asset else root / 'previews' / image_key(picture['url'])
        if path.is_file():
            pictures.append({'url': '/media/' + ('builtin/' + asset if asset else 'cached/' + path.name),
                             'path': str(path.resolve()), 'caption': picture.get('caption', value['name'])})
    value['screenshots'] = pictures
    return value

def media_path(url, root):
    prefix, _, filename = url.removeprefix('/media/').partition('/')
    require(filename and '/' not in filename and '\\' not in filename and filename.endswith('.png'), 'Unknown screenshot')
    if prefix == 'builtin':
        allowed = {p['asset'] for m in BUILTINS.values() for p in m['screenshots']}
        require(filename in allowed, 'Unknown screenshot')
        return MEDIA / filename
    require(prefix == 'cached' and len(filename) == 68 and all(c in '0123456789abcdef' for c in filename[:-4]), 'Unknown screenshot')
    return root / 'previews' / filename
