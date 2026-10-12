# Data and method

How to read the numbers in QPath, where they come from, and where they are weak.

## Sources

- **Google Jobs via SerpApi.** Each of the six subfields has one *core* search (used for headline counts and demand) and up to three *extended* searches (they find more postings, but are excluded from headline counts so a subfield with more searches does not look bigger). Postings are de-duplicated by title, company and location.
- **Google Scholar via SerpApi.** One search per subfield, sorted by date, about 20 recent papers each. Used only to extract qualitative research themes. Scholar's result totals are erratic (the same query returned 5,250 and 5,040 results on two runs), so the app never computes a trend or growth rate from them.
- **Data as of:** Live data captured on 10 October 2026 through SerpApi (38 live Google Jobs calls and 12 Google Scholar calls in total during development). 249 postings are stored; this includes postings first captured on 4 October from recorded real responses of the same searches.

## What the numbers mean

- **Active postings:** postings found by the subfield's core search and seen in the last 14 days. This is a sampled indicator, not a census: Google Jobs returns a limited number of pages per search, and busy subfields hit that cap (flagged as saturated).
- **Demand score:** ln(1 + active) / ln(1 + the largest active count across subfields), times 100. The log scale stops big subfields swamping small ones.
- **Readiness:** from the 18-question diagnostic. Points earned over points available per subfield, with difficulty 1, 2, 3 worth 1, 2, 3 points. "Not sure" scores 0 and there is no negative marking.
- **Interest:** your 1-5 slider, scaled to 0-100.
- **Path score:** 0.40 x interest + 0.30 x demand + 0.30 x readiness. The weights are a judgement, not fitted to data; they are named constants in the code. Declaring skills never changes path scores.
- **Opportunity match:** 60% overlap between your declared skills and the posting's extracted skills, plus 40% readiness. Shown only when you have declared skills and the posting has extracted skills.
- **NEW badge:** a posting first seen after you last pressed "Mark all as seen".
- **Trend sparklines:** drawn only once at least two days of snapshots exist.

## Where AI is used

- Gemini reads each posting (the first ~3,000 characters) and picks skills from a fixed 53-skill vocabulary, plus seniority, PhD and internship flags. Output is checked against a schema; unknown skills are dropped, and seniority and PhD are kept only when the text states them.
- Gemini reads Scholar titles and snippets and proposes 3-5 research themes with the papers that support them.
- Gemini writes path explanations from supplied evidence only. It never produces a score or a ranking. If an explanation contains a number that is not in the evidence, or the model call fails or the daily quota is gone, the app shows a plain template, labelled as a template.

## Accuracy checks

- **Extraction spot check, before the flag fix:** 20 postings sampled at random (seed 42, de-duplicated by title and company), one reviewer (the author), reading the same text the model saw. 13 of 20 had no unsupported skills, 19 of 20 had no clear omission, and 19 of 20 were quantum-related. Seniority, PhD or internship flags were judged wrong in 15 of 20, so flags now follow evidence-based rules. The sample is small: the 95% range for the unsupported-skill rate is about 18-57%.
- **After the fix:** Not re-measured after the fix; the numbers above describe the earlier extraction.
- **Quiz:** 18 questions drafted with LLM assistance, reviewed one by one by the author, and cross-checked by answering them without the key in a second model (DeepSeek); all 18 answers matched the key. There was no external expert review, and not every citation was checked against its source.

## Known limits

- The same job listed in several locations can appear more than once. Postings that are not quantum jobs leak in when a company name contains the word (for example QuantumBlack, an AI consultancy), and some results are academic faculty searches, policy roles or hardware assembly roles. All of these inflate counts a little; beyond the 20-posting check, how much is not measured.
- Skill extraction tends to add skills rather than miss them.
- The India view is thin and indicative only.
- Counts reflect search results at capture time and depend on Google's index and SerpApi availability.
- Free-tier Gemini quotas are small, so explanations may fall back to templates.
- A scheduler exists but is off by default; refreshes for this demo were run manually.
- The app is a decision aid. It makes no claim about hiring odds or salary.
