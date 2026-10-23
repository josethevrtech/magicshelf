"""The publisher's live directory of independently released creations."""
import re
from .contracts import require

OFFICIAL = 'https://raw.githubusercontent.com/josethevrtech/magicshelf/main/catalog.json'
DIRECTORY = 'https://raw.githubusercontent.com/josethevrtech/magicshelf/main/collections.json'


def catalogs(data):
    require(isinstance(data, dict) and data.get('schema_version') == 1, 'Unsupported collections directory')
    urls = data.get('catalogs')
    require(isinstance(urls, list) and len(urls) <= 64, 'Invalid collections directory')
    for url in urls:
        require(isinstance(url, str) and re.fullmatch(
            r'https://github\.com/josethevrtech/[A-Za-z0-9_.-]+/releases/latest/download/catalog\.json', url),
            'Invalid official collection URL')
    return list(dict.fromkeys(urls))
