"""M-10 spot check: review extraction against the full posting text (what Gemini saw)."""
import csv, json, os, random, sqlite3, textwrap

DB = 'backend/data/pathfinder.db'
VOC = 'backend/app/data/skills_vocab.json'
SEED, N, TEXT_LIMIT = 42, 20, 3000

con = sqlite3.connect(DB); con.row_factory = sqlite3.Row

# Vocabulary terms per skill id, used only to pre-flag skills with no lexical match in the text.
raw = json.load(open(VOC, encoding='utf-8'))
if isinstance(raw, dict) and 'skills' in raw:
    raw = raw['skills']
items = raw.items() if isinstance(raw, dict) else [(None, e) for e in raw]
terms = {}
for key, e in items:
    if not isinstance(e, dict):
        continue
    sid = e.get('id') or e.get('skill_id') or key
    nm = e.get('name') or e.get('label') or sid
    al = e.get('aliases') or e.get('synonyms') or []
    terms[sid] = {str(nm).lower(), str(sid).replace('_', ' ').lower()} | {str(a).lower() for a in al}

rows = [dict(r) for r in con.execute("select * from job_postings where extraction_status='done' order by id")]
seen, uniq = set(), []
for r in rows:                      # one row per (title, company): avoids reviewing duplicates twice
    k = (r['title'].strip().lower(), (r['company'] or '').strip().lower())
    if k not in seen:
        seen.add(k); uniq.append(r)
sample = random.Random(SEED).sample(uniq, min(N, len(uniq)))
sk = {}
for r in con.execute("select posting_id, skill_id from job_posting_skills"):
    sk.setdefault(r[0], []).append(r[1])


def ask(msg, ok):
    while True:
        a = input(msg).strip().lower()
        if a in ok:
            return a
        print('  enter one of:', '/'.join(sorted(ok)))


print(f"{len(rows)} extracted postings, {len(uniq)} unique by title+company; reviewing {len(sample)} (seed {SEED}).")
print("Vocabulary ids:", ', '.join(sorted(terms)) or '(could not read vocabulary)')
results = []
for i, r in enumerate(sample, 1):
    text = (r['description'] or '')[:TEXT_LIMIT]
    low = text.lower()
    print('\n' + '=' * 100)
    print(f"[{i}/{len(sample)}] id={r['id']}  {r['title']} @ {r['company']}")
    print(textwrap.fill(text, 110))
    print('-' * 100)
    ids = sk.get(r['id'], [])
    for s in ids:
        hit = any(t in low for t in terms.get(s, {s.replace('_', ' ')}))
        print(f"  skill: {s:<26} {'text match' if hit else '*** NO TEXT MATCH: check ***'}")
    if not ids:
        print('  skills: (none extracted)')
    print(f"  seniority={r['seniority']}  requires_phd={r['requires_phd']}  is_internship={r['is_internship']}")
    q = ask('a quantum-related job at all? y/n (q = stop and summarize): ', {'y', 'n', 'q'})
    if q == 'q':
        break
    a = ask('any extracted skill NOT supported by the text? y/n: ', {'y', 'n'})
    b = ask('any vocabulary skill clearly stated but MISSING? y/n/s(kip): ', {'y', 'n', 's'})
    c = ask('seniority / PhD / internship flag wrong? y/n/s(kip): ', {'y', 'n', 's'})
    results.append(dict(id=r['id'], title=r['title'], company=r['company'],
                        quantum=q, unsupported=a, missing=b, flags_wrong=c))

n = len(results)
if n == 0:
    raise SystemExit('nothing reviewed')
cnt = lambda k, v: sum(1 for x in results if x[k] == v)
os.makedirs('docs', exist_ok=True)
with open('docs/M10_SPOTCHECK.csv', 'w', newline='', encoding='utf-8') as f:
    w = csv.DictWriter(f, fieldnames=list(results[0]))
    w.writeheader(); w.writerows(results)
print('\n' + '=' * 100)
print(f"Reviewed {n} unique postings (seed {SEED}). Saved docs/M10_SPOTCHECK.csv")
print(f"  not quantum-related:                  {cnt('quantum', 'n')}/{n}")
print(f"  at least one unsupported skill:       {cnt('unsupported', 'y')}/{n}")
print(f"  at least one clear omission:          {cnt('missing', 'y')}/{n}  (skipped: {cnt('missing', 's')})")
print(f"  wrong seniority/PhD/internship flag:  {cnt('flags_wrong', 'y')}/{n}  (skipped: {cnt('flags_wrong', 's')})")
