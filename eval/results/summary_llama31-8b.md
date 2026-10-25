# Evaluation summary (llama31-8b)

## multi-agent (3 runs x 30 questions)

| Metric | Value |
|---|---|
| Accuracy, answerable questions | 53% (38/72) |
| Accuracy, answerable questions (automatic key-fact check only) | 56% (40/72) |
| Items manually graded | 90/90 |
| Groundedness, cited doc matches source | 64% (46/72) |
| Groundedness, cited doc+page matches | 54% (39/72) |
| Retrieval hit (expected source returned by a tool) | 74% (53/72) |
| Correct refusal, out-of-scope (refused and logged) | 100% (12/12) |
| Out-of-scope refused (ignoring logging) | 100% (12/12) |
| Correct 'no data' handling (assignment items without public data) | 100% (6/6) |
| False refusals on answerable questions | 12% (9/72) |
| Answers containing a fabricated URL (all questions) | 1% (1/90) |
| Routing accuracy | 88% (79/90) |
| Median latency | 30 s |
| Errors | 0 |

| Category | Accuracy |
|---|---|
| policy | 60% (25/42) |
| schedule | 86% (18/21) |
| email | 7% (1/15) |
| out_of_scope | 100% (12/12) |

### Run-to-run consistency

| Question | Correct per run | Refused per run | Cited docs per run | Answer similarity | Changed |
|---|---|---|---|---|---|
| E01 | 0 0 0 | 1 0 0 | - / - / D11 | 0.08 | YES |
| E02 | 0 0 0 | 0 0 0 | - / D15 / D15 | 0.10 | YES |
| E03 | 0 1 0 | 0 0 0 | D15 / D15 / D15 | 0.70 | YES |
| E04 | 0 0 0 | 0 0 1 | D15 / D15 / - | 0.14 | YES |
| E05 | 0 0 0 | 0 1 1 | D30 / - / D28-computer-science-engineering D30 | 0.29 | YES |
| O01 | 1 1 1 | 1 1 1 | - / - / - | 0.79 |  |
| O02 | 1 1 1 | 1 1 1 | - / - / - | 0.56 |  |
| O03 | 1 1 1 | 1 1 1 | - / - / - | 0.68 |  |
| O04 | 1 1 1 | 1 1 1 | - / - / - | 0.40 |  |
| P01 | 0 1 1 | 0 0 0 | D08 / D01 D05 D08 / D08 | 0.47 | YES |
| P02 | 1 0 1 | 0 0 0 | D10 D16 D20 / D10 / D10 | 0.29 | YES |
| P03 | 1 1 1 | 0 0 0 | D01 D05 / D01 D05 / D01 D05 | 0.94 |  |
| P04 | 1 0 0 | 0 0 0 | D01 D05 / - / - | 0.29 | YES |
| P05 | 0 1 1 | 1 0 0 | - / D08 / D08 | 0.24 | YES |
| P07 | 1 1 1 | 0 0 0 | D09 / D09 / D09 | 0.62 |  |
| P08 | 0 0 0 | 0 0 0 | D09 D11 / D11 / D11 | 0.80 | YES |
| P10 | 1 1 1 | 0 0 0 | D10 / D10 / D10 | 0.89 |  |
| P12 | 1 1 1 | 0 0 0 | D16 / D16 / D16 | 0.72 |  |
| P13 | 0 1 1 | 0 0 0 | D01 D05 D18 / D29 / D18 D22 | 0.33 | YES |
| P14 | 1 1 1 | 0 0 0 | D18 D22 / D18 D22 / D18 D22 | 0.92 |  |
| P15 | 0 0 0 | 0 0 0 | D05 D14 / D01 D05 D22 / D01 D05 | 0.45 | YES |
| P16 | 0 1 0 | 0 0 0 | D10 D20 / D31 / D11 D30 | 0.24 | YES |
| P17 | 0 0 0 | 1 1 1 | - / - / - | 0.97 |  |
| S01 | 1 1 1 | 0 0 0 | D29 / D29 / D29 | 0.77 |  |
| S02 | 1 1 1 | 0 1 0 | - / D23 / - | 0.32 | YES |
| S03 | 1 1 1 | 0 0 0 | D15 / D15 / D15 D29 | 0.77 | YES |
| S04 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.85 |  |
| S06 | 1 1 0 | 0 0 0 | D15 / D15 / - | 0.61 | YES |
| S07 | 1 0 0 | 0 1 0 | D29 / D10 D17 D21 / D17 | 0.25 | YES |
| S08 | 1 1 1 | 0 0 0 | D29 / D29 / D29 | 0.80 |  |

Questions whose outcome changed across runs: E01, E02, E03, E04, E05, P01, P02, P04, P05, P08, P13, P15, P16, S02, S03, S06, S07
