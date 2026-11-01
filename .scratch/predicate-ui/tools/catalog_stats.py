# 規格 4 用:目錄的鍵唯一性、名字裡的特殊字元、效果位 0 張的查詢。跑法:python .scratch/predicate-ui/tools/catalog_stats.py
import json, collections, re, sys, hashlib
sys.stdout.reconfigure(encoding='utf-8')
raw = open('data/action_frames.json','rb').read()
print('export md5', hashlib.md5(raw).hexdigest())
d = json.loads(raw.decode('utf-8'))
cat = d['目錄']
print('rows', len(cat), 'predicate rows', sum(1 for r in cat if r['predicate']), 'null', sum(1 for r in cat if not r['predicate']))
qs = [r for r in cat if r['predicate']]
names = collections.Counter(r['name'] for r in cat)
print('dup names all', [n for n,c in names.items() if c>1][:20])
qnames = collections.Counter(r['name'] for r in qs)
print('dup names queries', [n for n,c in qnames.items() if c>1])
paths = collections.Counter('›'.join(r['path']) for r in cat)
print('dup paths all', [p for p,c in paths.items() if c>1])
qpaths = collections.Counter('›'.join(r['path']) for r in qs)
print('dup paths queries', [p for p,c in qpaths.items() if c>1])
print('name==last seg', sum(1 for r in cat if r['path'][-1]==r['name']), 'of', len(cat))
for ch in '›:|;,/~.=&%+-()':
    hit=[r['name'] for r in qs if ch in r['name']]
    print(repr(ch), len(hit), hit[:3])
zero=[r for r in qs if r['cards']['效果']==0]
print('zero effect', len(zero))
for r in zero: print('  ',r['name'],r['cards'])
longest=sorted(qs,key=lambda r:len('›'.join(r['path'])))[-1]
print('longest path', '›'.join(longest['path']), len(longest['name']))
