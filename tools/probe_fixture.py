import urllib.request
import sys

fixture_id = sys.argv[1] if len(sys.argv) > 1 else '600930'
url = f'https://resultados.fpf.pt/Competition/GetClassificationAndMatchesByFixture?fixtureId={fixture_id}'
req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
with urllib.request.urlopen(req) as r:
    data = r.read()
    ct = r.headers.get('Content-Type')
    print('status', r.status, 'ctype', ct, 'len', len(data))
    text = data.decode('utf-8', 'ignore')
open(f'cache/fixture_{fixture_id}.html', 'w', encoding='utf-8').write(text)
print(text[:1000])

