from __future__ import annotations
import json
from pathlib import Path

base = Path('/home/albert/clawd/projects/hackathon-review')
rows = json.loads((base/'data'/'genlayer-usage-report.json').read_text())

core = {1,4,6,7,8,9,10,18,21,23,25,26,30,31,32,33,34}
meaningful = {2,5,11,14,16,19,36}
weak = {28}

manual_roles = {
1:'Contract/security judgment layer',
2:'AI advisor / retirement decision layer',
3:'Not proven',
4:'Debate evaluation contract execution',
5:'AI wallet classification / scam detection',
6:'Prediction market resolution consensus',
7:'On-chain AI judging of builds',
8:'Cross-chain prediction-market resolution',
9:'AI-consensus robotics mission validation',
10:'AI settlement of prediction challenges',
11:'Intelligent-contract game / trivia logic',
12:'Not proven',
13:'Not proven',
14:'GenLayer summary / verification in aid flow',
15:'Not proven',
16:'AI engine / agent backend',
17:'Not proven',
18:'Validator consensus for payout/release',
19:'Validator/oracle verification services',
20:'Arbitration theme only; implementation unproven',
21:'Treasury governance / policy consensus',
22:'Not proven',
23:'AI council validation of campaigns',
24:'Not proven',
25:'Prediction-market intelligent contracts',
26:'Bounty / PR verification consensus',
27:'Not proven',
28:'Future-facing RPC hook only',
29:'Not proven',
30:'AI execution strategy via Optimistic Democracy',
31:'Freelance escrow verification / dispute resolution',
32:'Freelance escrow intelligent contract',
33:'Compliance / audit verification consensus',
34:'Payment approval / merchant audit',
35:'Not proven',
36:'Verification / credentialing layer',
}

def classify(row):
    i = row['id']
    if i in core:
        cat = 'core'
    elif i in meaningful:
        cat = 'meaningful'
    elif i in weak:
        cat = 'weak/future'
    else:
        cat = 'unclear'
    return cat

def confidence(row):
    evidence = len(row.get('evidence', []))
    checked = row.get('sourcesChecked', {})
    count = sum(1 for v in checked.values() if v)
    if classify(row) == 'unclear':
        return 'low'
    if evidence >= 2 and count >= 2:
        return 'high'
    if evidence >= 1:
        return 'medium'
    return 'low'

def serious(cat):
    return {'core':'yes','meaningful':'maybe','weak/future':'no','unclear':'no'}[cat]

rank_order = {'core':0,'meaningful':1,'weak/future':2,'unclear':3}
for r in rows:
    r['genlayerCategory'] = classify(r)
    r['role'] = manual_roles[r['id']]
    r['confidence'] = confidence(r)
    r['seriousGenLayerProject'] = serious(r['genlayerCategory'])

rows = sorted(rows, key=lambda r: (rank_order[r['genlayerCategory']], r['id']))

md = ['# GenLayer judging table\n', '| # | Project | Category | GenLayer role | Confidence | Serious GenLayer project? |', '|---:|---|---|---|---|---|']
for r in rows:
    md.append(f"| {r['id']} | {r['projectName']} | {r['genlayerCategory']} | {r['role']} | {r['confidence']} | {r['seriousGenLayerProject']} |")

(base/'notes'/'genlayer-judging-table.md').write_text('\n'.join(md) + '\n')
(base/'data'/'genlayer-judging-table.json').write_text(json.dumps(rows, indent=2, ensure_ascii=False))
print('wrote', len(rows))
