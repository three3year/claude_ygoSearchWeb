"""多子句切開後非動作左半五類(票 02 Comments)的處數與左右半解析狀態;讀 data/action_structure.json。"""
import json, re, collections, sys
d=json.load(open('data/action_structure.json',encoding='utf-8'))
pats={'1 を選択し':r'を選択し$','2 を対象とし':r'を対象とし$','3 素材とし':r'素材とし$','4 異なり':r'異なり$'}
stat=collections.defaultdict(lambda: collections.Counter()); ex=collections.defaultdict(list)
def walk(segs):
    for s in segs: yield s
for c in d:
    for b in c.get('blocks',[]):
        segs=b.get('segments',[])
        for i,s in enumerate(segs):
            t=b['text'][s['span'][0]:s['span'][1]].rstrip('、')
            for k,p in pats.items():
                if re.search(p,t):
                    L='L解析不出' if s.get('unparsed') else 'L解析出'
                    nxt=segs[i+1] if i+1<len(segs) else None
                    R='R無' if not nxt else ('R解析不出:'+nxt['unparsed'].get('reason','')) if nxt.get('unparsed') else 'R解析出'
                    stat[k][L]+=1; stat[k][R]+=1
                    if len(ex[k])<2: ex[k].append((c['id'],c['name_ja'],t[-40:], b['text'][nxt['span'][0]:nxt['span'][1]][:40] if nxt else '', s.get('unparsed',{}).get('reason')))
for k in sorted(stat):
    print(k, dict(stat[k].most_common(8)))
    for e in ex[k]: print('   ',e)
