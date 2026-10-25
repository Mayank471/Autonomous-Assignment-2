# Evaluation summary (v1-qwen3-8b)

## single-agent (1 runs x 30 questions)

| Metric | Value |
|---|---|
| Accuracy, answerable questions | 52% (12/23) |
| Accuracy, answerable questions (automatic key-fact check only) | 57% (13/23) |
| Items manually graded | 30/30 |
| Groundedness, cited doc matches source | 61% (14/23) |
| Groundedness, cited doc+page matches | 48% (11/23) |
| Retrieval hit (expected source returned by a tool) | 52% (12/23) |
| Correct refusal, out-of-scope (refused and logged) | 100% (4/4) |
| Out-of-scope refused (ignoring logging) | 100% (4/4) |
| Correct 'no data' handling (assignment items without public data) | 67% (2/3) |
| False refusals on answerable questions | 13% (3/23) |
| Answers containing a fabricated URL (all questions) | 17% (5/30) |
| Median latency | 31 s |
| Errors | 0 |

| Category | Accuracy |
|---|---|
| policy | 40% (6/15) |
| schedule | 50% (3/6) |
| email | 100% (5/5) |
| out_of_scope | 100% (4/4) |

### Run-to-run consistency

| Question | Correct per run | Refused per run | Cited docs per run | Answer similarity | Changed |
|---|---|---|---|---|---|

Questions whose outcome changed across runs: none
