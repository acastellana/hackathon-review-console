from __future__ import annotations
import json, re
from pathlib import Path

BASE = Path('/home/albert/clawd/projects/hackathon-review/data')
subs = {x['id']: x for x in json.loads((BASE/'submissions.json').read_text())}
repos = {x['id']: x for x in json.loads((BASE/'repo-signals.json').read_text())}
trs = {x['id']: x for x in json.loads((BASE/'video-transcripts.json').read_text())}
rubric = json.loads((BASE/'scoring-rubric.json').read_text())['dimensions']

verb_noise = re.compile(r'\b(uh|um|you know|like|so|okay|right)\b', re.I)

def first_sentences(text, n=2):
    if not text:
        return []
    text = re.sub(r'\s+', ' ', text).strip()
    text = verb_noise.sub('', text)
    parts = re.split(r'(?<=[.!?])\s+', text)
    out = []
    for p in parts:
        p = p.strip(' -')
        if len(p) > 25 and p not in out:
            out.append(p)
        if len(out) >= n:
            break
    return out

results = []
for sid, sub in subs.items():
    repo = repos.get(sid, {})
    tr = trs.get(sid, {})
    seed_parts = []
    if repo.get('description'):
        seed_parts.append(repo['description'].strip())
    if tr.get('title') and tr.get('title') != sub['projectName']:
        seed_parts.append(tr['title'].strip())
    if tr.get('transcriptText'):
        seed_parts.extend(first_sentences(tr['transcriptText'], 2))
    elif tr.get('summarySeed'):
        seed_parts.extend(first_sentences(tr['summarySeed'], 2))
    summary = ' '.join(seed_parts).strip()
    if not summary:
        summary = f"{sub['projectName']} is a hackathon submission in {', '.join(sub.get('tracks', [])[:2]) or 'the listed tracks'}."
    # heuristic scorecard 0-10
    scorecard = {
        'problem_clarity': 7.2 if tr.get('transcriptStatus') == 'ok' else 5.8,
        'demo_explainability': 7.4 if tr.get('transcriptStatus') == 'ok' else 5.0,
        'technical_depth': 7.0 if repo.get('repoExists') else 3.5,
        'product_completeness': 7.1 if repo.get('homepage') or tr.get('transcriptStatus') == 'ok' else 5.6,
        'code_quality': 4.0 + (1.5 if repo.get('hasReadme') else 0) + (1.5 if repo.get('hasTestsHeuristic') else 0) + (1.0 if repo.get('hasLicense') else 0) + (1.0 if repo.get('hasCIHeuristic') else 0),
        'innovation': 6.5,
        'genlayer_fit': 7.0 if any('GenLayer' in t for t in sub.get('tracks', [])) else 5.5,
    }
    scorecard = {k: round(max(0, min(10, v)), 1) for k, v in scorecard.items()}
    total = 0
    for dim in rubric:
        total += scorecard[dim['key']] * dim['weight']
    total = round(total / 10, 1)
    judge_notes = []
    if tr.get('transcriptStatus') == 'ok':
        judge_notes.append('Transcript available — fast skim possible before opening the full demo.')
    else:
        judge_notes.append(f"Transcript unavailable or partial ({tr.get('transcriptStatus', 'unknown')}).")
    if repo.get('repoExists'):
        judge_notes.append(f"Repo detected in {repo.get('primaryLanguage') or 'unknown language'}; pushed {repo.get('lastUpdate') or 'unknown date' }.")
    else:
        judge_notes.append('Repo could not be validated automatically.')
    if repo.get('hasReadme'):
        judge_notes.append('README present.')
    if not repo.get('hasLicense'):
        judge_notes.append('No license detected.')
    if repo.get('riskFlags'):
        judge_notes.append('Main risk flags: ' + '; '.join(repo['riskFlags'][:3]) + '.')
    results.append({
        'id': sid,
        'projectName': sub['projectName'],
        'summary': summary[:900],
        'judgeNotes': judge_notes,
        'scorecard': scorecard,
        'totalScore': total,
    })

(BASE/'project-summaries.json').write_text(json.dumps(sorted(results, key=lambda x: x['id']), indent=2, ensure_ascii=False))
print('wrote', len(results))
