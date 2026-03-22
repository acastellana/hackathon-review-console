from __future__ import annotations
import json
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse
import requests

BASE = Path('/home/albert/clawd/projects/hackathon-review')
DATA = BASE / 'data'
CACHE = BASE / 'cache'
CACHE.mkdir(parents=True, exist_ok=True)
subs = json.loads((DATA / 'submissions.json').read_text())

session = requests.Session()
session.headers.update({
    'User-Agent': 'hackathon-review-bob/1.0',
    'Accept': 'application/vnd.github+json',
})

def gh_repo_parts(url: str):
    parsed = urlparse(url)
    parts = [p for p in parsed.path.strip('/').split('/') if p]
    if len(parts) >= 2:
        return parts[0], parts[1].removesuffix('.git')
    return None, None

repo_signals = []
transcripts = []
summary_inputs = []

for sub in subs:
    rid = sub['id']
    proj = sub['projectName']
    github = sub['githubUrl']
    owner, repo = gh_repo_parts(github)
    signal = {
        'id': rid,
        'projectName': proj,
        'githubUrl': github,
        'repoExists': False,
        'stars': None,
        'forks': None,
        'watchers': None,
        'openIssues': None,
        'primaryLanguage': None,
        'lastUpdate': None,
        'defaultBranch': None,
        'hasReadme': None,
        'hasLicense': None,
        'hasTestsHeuristic': None,
        'hasDocsHeuristic': None,
        'hasCIHeuristic': None,
        'topicTags': [],
        'homepage': None,
        'sizeKb': None,
        'description': None,
        'polishSignals': [],
        'riskFlags': [],
        'fetchError': None,
    }
    if owner and repo:
        try:
            r = session.get(f'https://api.github.com/repos/{owner}/{repo}', timeout=20)
            if r.ok:
                j = r.json()
                signal.update({
                    'repoExists': True,
                    'stars': j.get('stargazers_count'),
                    'forks': j.get('forks_count'),
                    'watchers': j.get('subscribers_count') or j.get('watchers_count'),
                    'openIssues': j.get('open_issues_count'),
                    'primaryLanguage': j.get('language'),
                    'lastUpdate': j.get('pushed_at'),
                    'defaultBranch': j.get('default_branch'),
                    'hasLicense': bool(j.get('license')),
                    'topicTags': j.get('topics') or [],
                    'homepage': j.get('homepage'),
                    'sizeKb': j.get('size'),
                    'description': j.get('description'),
                })
                if signal['homepage']:
                    signal['polishSignals'].append('homepage set')
                if signal['hasLicense']:
                    signal['polishSignals'].append('license declared')
                readme = session.get(f'https://api.github.com/repos/{owner}/{repo}/readme', timeout=20)
                signal['hasReadme'] = readme.ok
                if readme.ok:
                    signal['polishSignals'].append('readme present')
                contents = session.get(f'https://api.github.com/repos/{owner}/{repo}/contents', timeout=20)
                names = []
                if contents.ok and isinstance(contents.json(), list):
                    names = [x.get('name','').lower() for x in contents.json()]
                signal['hasTestsHeuristic'] = any(n in names or n.startswith('test') for n in ['test','tests','__tests__','spec','specs'])
                signal['hasDocsHeuristic'] = any(n in names for n in ['docs','documentation']) or any('docs' in n for n in names)
                signal['hasCIHeuristic'] = '.github' in names or '.gitlab-ci.yml' in names
                if signal['hasTestsHeuristic']:
                    signal['polishSignals'].append('tests folder heuristic')
                else:
                    signal['riskFlags'].append('no obvious tests folder')
                if signal['hasCIHeuristic']:
                    signal['polishSignals'].append('ci/config heuristic')
                if not signal['hasLicense']:
                    signal['riskFlags'].append('no license detected')
                if not signal['hasReadme']:
                    signal['riskFlags'].append('no readme detected')
            else:
                signal['fetchError'] = f'GitHub API {r.status_code}'
                signal['riskFlags'].append(f'github api {r.status_code}')
        except Exception as e:
            signal['fetchError'] = str(e)
            signal['riskFlags'].append('repo fetch failed')
    else:
        signal['fetchError'] = 'bad github url'
        signal['riskFlags'].append('bad github url')
    repo_signals.append(signal)

    demo = sub['demoUrl']
    transcript_entry = {
        'id': rid,
        'projectName': proj,
        'demoUrl': demo,
        'platform': None,
        'title': None,
        'uploader': None,
        'durationSeconds': None,
        'transcriptStatus': 'not_attempted',
        'transcriptText': None,
        'summarySeed': None,
        'notes': [],
    }
    lower = demo.lower()
    if 'youtu' in lower:
        transcript_entry['platform'] = 'youtube'
    elif 'loom.com' in lower:
        transcript_entry['platform'] = 'loom'
    elif 'vimeo.com' in lower:
        transcript_entry['platform'] = 'vimeo'
    elif 'canva.com' in lower:
        transcript_entry['platform'] = 'canva'
    elif 'descript.com' in lower:
        transcript_entry['platform'] = 'descript'
    elif demo.lower().endswith('.mp4'):
        transcript_entry['platform'] = 'direct_mp4'
    else:
        transcript_entry['platform'] = 'other'

    try:
        info_proc = subprocess.run(
            ['yt-dlp', '--dump-single-json', '--skip-download', demo],
            capture_output=True, text=True, timeout=120
        )
        if info_proc.returncode == 0 and info_proc.stdout.strip():
            info = json.loads(info_proc.stdout)
            transcript_entry['title'] = info.get('title')
            transcript_entry['uploader'] = info.get('uploader') or info.get('channel')
            transcript_entry['durationSeconds'] = info.get('duration')
            desc = info.get('description')
            if desc:
                transcript_entry['summarySeed'] = desc[:4000]
            sub_cache = CACHE / f'transcript_{rid}.txt'
            sub_proc = subprocess.run(
                ['yt-dlp', '--skip-download', '--write-auto-subs', '--write-subs', '--sub-langs', 'en.*,es.*,en,es', '-o', str(CACHE / f'{rid}.%(ext)s'), demo],
                capture_output=True, text=True, timeout=180
            )
            candidates = sorted(CACHE.glob(f'{rid}*.vtt')) + sorted(CACHE.glob(f'{rid}*.srv3')) + sorted(CACHE.glob(f'{rid}*.ttml'))
            if candidates:
                txt = candidates[0].read_text(errors='ignore')
                cleaned = re.sub(r'<[^>]+>', ' ', txt)
                cleaned = re.sub(r'WEBVTT|Kind:.*|Language:.*|\d\d:\d\d:\d\d\.\d+\s+-->\s+\d\d:\d\d:\d\d\.\d+', ' ', cleaned)
                cleaned = re.sub(r'\s+', ' ', cleaned).strip()
                if cleaned:
                    transcript_entry['transcriptStatus'] = 'ok'
                    transcript_entry['transcriptText'] = cleaned[:40000]
                    sub_cache.write_text(cleaned)
                else:
                    transcript_entry['transcriptStatus'] = 'empty_subtitles'
            else:
                transcript_entry['transcriptStatus'] = 'no_subtitles_found'
                transcript_entry['notes'].append('yt-dlp metadata ok, subtitles unavailable')
        else:
            transcript_entry['transcriptStatus'] = 'metadata_failed'
            stderr = info_proc.stderr.strip().splitlines()[-1] if info_proc.stderr.strip() else 'unknown'
            transcript_entry['notes'].append(stderr[:500])
    except Exception as e:
        transcript_entry['transcriptStatus'] = 'error'
        transcript_entry['notes'].append(str(e))
    transcripts.append(transcript_entry)

    summary_inputs.append({
        'id': rid,
        'projectName': proj,
        'repoDescription': signal['description'],
        'demoTitle': transcript_entry['title'],
        'summarySeed': transcript_entry['summarySeed'],
        'transcriptStatus': transcript_entry['transcriptStatus'],
        'transcriptPreview': (transcript_entry['transcriptText'] or '')[:1200],
    })

(DATA / 'repo-signals.json').write_text(json.dumps(repo_signals, indent=2, ensure_ascii=False))
(DATA / 'video-transcripts.json').write_text(json.dumps(transcripts, indent=2, ensure_ascii=False))
(DATA / 'summary-inputs.json').write_text(json.dumps(summary_inputs, indent=2, ensure_ascii=False))

rubric = {
    'dimensions': [
        {'key': 'problem_clarity', 'label': 'Problem clarity', 'weight': 15, 'guide': 'Is the pain point obvious and worth solving?'},
        {'key': 'demo_explainability', 'label': 'Demo explainability', 'weight': 15, 'guide': 'Can a judge understand the product quickly from the demo?'},
        {'key': 'technical_depth', 'label': 'Technical depth', 'weight': 20, 'guide': 'Does the implementation show real engineering substance?'},
        {'key': 'product_completeness', 'label': 'Product completeness', 'weight': 15, 'guide': 'Does it feel like a usable product rather than a concept?'},
        {'key': 'code_quality', 'label': 'Code quality', 'weight': 15, 'guide': 'Repo organization, docs, tests, maintainability signals.'},
        {'key': 'innovation', 'label': 'Innovation', 'weight': 10, 'guide': 'Is there a differentiated insight or novel approach?'},
        {'key': 'genlayer_fit', 'label': 'GenLayer / track fit', 'weight': 10, 'guide': 'Is the project genuinely aligned to the GenLayer / entered tracks?'}
    ],
    'scale': '0-10 per dimension',
    'notes': [
        'Automated signals help pre-score code quality and polish, but final judging should still include human review of demo and track fit.',
        'Missing repo/demo assets should reduce confidence, not automatically zero the project.'
    ]
}
(DATA / 'scoring-rubric.json').write_text(json.dumps(rubric, indent=2, ensure_ascii=False))

(Path(BASE / 'notes' / 'scoring-method.md')).write_text(
    '# Scoring method\n\n'
    '- 7 dimensions weighted to 100.\n'
    '- Automated repo signals: README, license, tests/docs/CI heuristics, language, last push, stars/forks, homepage.\n'
    '- Automated transcript attempts: via yt-dlp metadata + available subtitles when accessible.\n'
    '- Human review still needed for actual product merit, live-demo coherence, and whether GenLayer usage is real or cosmetic.\n'
)

print('done', len(subs), 'submissions')
