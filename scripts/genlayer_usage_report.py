from __future__ import annotations
import json, re, base64
from pathlib import Path
from urllib.parse import urlparse
import requests

BASE = Path('/home/albert/clawd/projects/hackathon-review/data')
subs = json.loads((BASE/'submissions.json').read_text())
trs = {x['id']: x for x in json.loads((BASE/'video-transcripts.json').read_text())}
repo_signals = {x['id']: x for x in json.loads((BASE/'repo-signals.json').read_text())}

session = requests.Session()
session.headers.update({'User-Agent': 'bob-genlayer-usage/1.0', 'Accept': 'application/vnd.github+json'})

KEYWORDS = [
    'genlayer', 'intelligent contract', 'intelligent contracts', 'genvm', 'internetcourt',
    'consensus of llms', 'consensus of llm', 'ai validator', 'validators', 'simulator',
    'genlayer studio', 'jury', 'ai consensus', 'deterministic llm'
]

IMPL_HINTS = [
    ('smart contract', 'Uses on-chain smart contracts / contracts as part of the flow.'),
    ('oracle', 'Uses an oracle-style external verification / data input flow.'),
    ('agent', 'Uses AI agents as part of the product behavior.'),
    ('arbitration', 'Uses dispute resolution / arbitration concepts that may map well to GenLayer.'),
    ('prediction market', 'Uses market-style decision flows that may benefit from AI-verifiable outcomes.'),
    ('wallet', 'Includes wallet / on-chain transaction flow.'),
    ('audit', 'Uses AI-assisted code or security review.'),
]

def gh_parts(url: str):
    parts = [p for p in urlparse(url).path.strip('/').split('/') if p]
    if len(parts) >= 2:
        return parts[0], parts[1].removesuffix('.git')
    return None, None

def fetch_readme(owner, repo):
    if not owner or not repo:
        return None
    try:
        r = session.get(f'https://api.github.com/repos/{owner}/{repo}/readme', timeout=20)
        if not r.ok:
            return None
        j = r.json()
        content = j.get('content')
        if j.get('encoding') == 'base64' and content:
            return base64.b64decode(content).decode('utf-8', errors='ignore')
    except Exception:
        return None
    return None

def clip(text, limit=3000):
    text = re.sub(r'\s+', ' ', text or '').strip()
    return text[:limit]

report = []
md = ['# GenLayer usage review\n']
for sub in subs:
    sid = sub['id']
    tr = trs.get(sid, {})
    rs = repo_signals.get(sid, {})
    owner, repo = gh_parts(sub['githubUrl'])
    readme = fetch_readme(owner, repo) or ''
    transcript = tr.get('transcriptText') or ''
    combined = '\n'.join([sub['projectName'], rs.get('description') or '', readme[:12000], transcript[:12000]])
    low = combined.lower()

    hits = []
    for kw in KEYWORDS:
        if kw in low:
            hits.append(kw)

    evidence = []
    for source_name, text in [('repo description', rs.get('description') or ''), ('README', readme), ('transcript', transcript)]:
        if not text:
            continue
        for kw in ['genlayer', 'intelligent contract', 'internetcourt', 'jury', 'ai consensus', 'validator']:
            idx = text.lower().find(kw)
            if idx != -1:
                start = max(0, idx - 120)
                end = min(len(text), idx + 220)
                evidence.append(f'{source_name}: ' + clip(text[start:end], 500))
                break

    impl_hints = [msg for kw, msg in IMPL_HINTS if kw in low]
    tracks = sub.get('tracks', [])

    if 'genlayer' in low or 'intelligent contract' in low or 'internetcourt' in low or 'genvm' in low:
        status = 'explicit'
    elif any('GenLayer' in t for t in tracks):
        status = 'track-entry-only'
    else:
        status = 'unclear'

    likely = None
    if status == 'explicit':
        if 'arbitration' in low or 'jury' in low or 'dispute' in low:
            likely = 'Likely uses GenLayer for AI-based arbitration / judgment.'
        elif 'audit' in low or 'security' in low:
            likely = 'Likely uses GenLayer for AI-evaluated code / audit decisions.'
        elif 'agent' in low:
            likely = 'Likely uses GenLayer as an AI-agent / intelligent-contract backend.'
        else:
            likely = 'GenLayer appears to be part of the product architecture, but exact technical usage still needs human verification.'
    elif status == 'track-entry-only':
        likely = 'Submitted in the GenLayer track, but the currently accessible evidence does not yet prove how GenLayer is used.'
    else:
        likely = 'No clear GenLayer usage found in the currently accessible evidence.'

    report.append({
        'id': sid,
        'projectName': sub['projectName'],
        'status': status,
        'tracks': tracks,
        'keywordHits': hits,
        'likelyUsage': likely,
        'implementationHints': impl_hints,
        'evidence': evidence[:3],
        'sourcesChecked': {
            'repoDescription': bool(rs.get('description')),
            'readme': bool(readme),
            'transcript': bool(transcript),
        }
    })

    md.append(f"## {sid}. {sub['projectName']}\n")
    md.append(f"- **Status:** {status}\n")
    md.append(f"- **Likely GenLayer usage:** {likely}\n")
    if impl_hints:
        md.append(f"- **Implementation hints:** {' | '.join(impl_hints[:3])}\n")
    if evidence:
        for ev in evidence[:2]:
            md.append(f"- **Evidence:** {ev}\n")
    else:
        md.append("- **Evidence:** No direct GenLayer mention found in accessible README/transcript/description.\n")
    md.append('\n')

(BASE/'genlayer-usage-report.json').write_text(json.dumps(report, indent=2, ensure_ascii=False))
(Path('/home/albert/clawd/projects/hackathon-review/notes/genlayer-usage-report.md')).write_text('\n'.join(md))
print('wrote', len(report))
