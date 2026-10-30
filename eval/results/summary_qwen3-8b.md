# Evaluation summary (qwen3-8b)

## single-agent (3 runs x 30 questions)

| Metric | Value |
|---|---|
| Accuracy, answerable questions | 58% (42/72) |
| Accuracy, answerable questions (automatic key-fact check only) | 58% (42/72) |
| Items manually graded | 90/90 |
| Groundedness, cited doc matches source | 64% (46/72) |
| Groundedness, cited doc+page matches | 58% (42/72) |
| Retrieval hit (expected source returned by a tool) | 54% (39/72) |
| Correct refusal, out-of-scope (refused and logged) | 100% (12/12) |
| Out-of-scope refused (ignoring logging) | 100% (12/12) |
| Correct 'no data' handling (assignment items without public data) | 67% (4/6) |
| False refusals on answerable questions | 28% (20/72) |
| Answers containing a fabricated URL (all questions) | 0% (0/90) |
| Median latency | 33 s |
| Errors | 0 |

| Category | Accuracy |
|---|---|
| policy | 43% (18/42) |
| schedule | 76% (16/21) |
| email | 80% (12/15) |
| out_of_scope | 100% (12/12) |

### Run-to-run consistency

| Question | Correct per run | Refused per run | Cited docs per run | Answer similarity | Changed |
|---|---|---|---|---|---|
| E01 | 1 1 1 | 0 0 0 | - / - / - | 0.98 |  |
| E02 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 1.00 |  |
| E03 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 1.00 |  |
| E04 | 0 0 0 | 0 0 0 | D15 / D15 / D15 | 0.63 |  |
| E05 | 1 1 1 | 0 0 0 | D28-computer-science-engineering D30 / D28-computer-science-engineering D30 / D28-computer-science-engineering D30 | 1.00 |  |
| O01 | 1 1 1 | 1 1 1 | - / - / - | 0.87 |  |
| O02 | 1 1 1 | 1 1 1 | - / - / - | 0.44 |  |
| O03 | 1 1 1 | 1 1 1 | - / - / - | 0.80 |  |
| O04 | 1 1 1 | 1 1 1 | - / - / - | 0.52 |  |
| P01 | 0 0 0 | 0 0 0 | D01 D08 / D01 D05 D08 D10 / D01 D05 D08 D10 | 0.80 | YES |
| P02 | 0 1 1 | 0 0 0 | D01 D10 D16 D20 / D01 D20 / D01 D16 D20 | 0.50 | YES |
| P03 | 0 0 0 | 1 1 1 | - / - / - | 0.20 |  |
| P04 | 1 1 1 | 0 0 0 | D01 D05 / D01 / D01 D05 | 0.80 | YES |
| P05 | 1 1 1 | 0 0 0 | D08 / D08 / D05 D08 | 0.57 | YES |
| P07 | 0 0 0 | 1 1 1 | - / - / - | 0.59 |  |
| P08 | 0 0 0 | 0 1 0 | D11 / D11 / D11 | 0.74 | YES |
| P10 | 1 1 1 | 0 0 0 | D01 D05 / D05 / D05 | 0.82 | YES |
| P12 | 0 1 0 | 1 0 1 | - / D16 / - | 0.32 | YES |
| P13 | 1 1 1 | 0 0 0 | D29 / D29 / D29 | 0.57 |  |
| P14 | 0 0 0 | 1 0 1 | - / D29 / - | 0.29 | YES |
| P15 | 1 1 1 | 0 0 0 | D01 / D01 / D01 | 0.64 |  |
| P16 | 0 0 0 | 1 1 1 | - / - / - | 0.46 |  |
| P17 | 0 0 0 | 1 1 1 | - / - / - | 0.87 |  |
| S01 | 1 1 1 | 0 0 0 | D29 / D29 / - | 0.64 | YES |
| S02 | 0 0 1 | 0 0 0 | D01 D11 D30 / D01 D11 D30 / D01 D11 D30 | 0.90 | YES |
| S03 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.77 |  |
| S04 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 1.00 |  |
| S06 | 0 0 0 | 1 1 1 | - / - / - | 1.00 |  |
| S07 | 1 1 1 | 0 0 0 | D29 / D29 / D29 | 0.98 |  |
| S08 | 1 1 1 | 0 0 0 | - / - / - | 1.00 |  |

Questions whose outcome changed across runs: P01, P02, P04, P05, P08, P10, P12, P14, S01, S02

## multi-agent (3 runs x 30 questions)

| Metric | Value |
|---|---|
| Accuracy, answerable questions | 79% (57/72) |
| Accuracy, answerable questions (automatic key-fact check only) | 79% (57/72) |
| Items manually graded | 90/90 |
| Groundedness, cited doc matches source | 83% (60/72) |
| Groundedness, cited doc+page matches | 76% (55/72) |
| Retrieval hit (expected source returned by a tool) | 75% (54/72) |
| Correct refusal, out-of-scope (refused and logged) | 100% (12/12) |
| Out-of-scope refused (ignoring logging) | 100% (12/12) |
| Correct 'no data' handling (assignment items without public data) | 100% (6/6) |
| False refusals on answerable questions | 8% (6/72) |
| Answers containing a fabricated URL (all questions) | 0% (0/90) |
| Routing accuracy | 87% (78/90) |
| Median latency | 40 s |
| Errors | 0 |

| Category | Accuracy |
|---|---|
| policy | 64% (27/42) |
| schedule | 100% (21/21) |
| email | 100% (15/15) |
| out_of_scope | 100% (12/12) |

### Run-to-run consistency

| Question | Correct per run | Refused per run | Cited docs per run | Answer similarity | Changed |
|---|---|---|---|---|---|
| E01 | 1 1 1 | 0 0 0 | - / - / - | 0.87 |  |
| E02 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.90 |  |
| E03 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.90 |  |
| E04 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.77 |  |
| E05 | 1 1 1 | 0 0 0 | D28-computer-science-engineering D30 / D28-computer-science-engineering D30 / D28-computer-science-engineering D30 | 0.85 |  |
| O01 | 1 1 1 | 1 1 1 | - / - / - | 0.83 |  |
| O02 | 1 1 1 | 1 1 1 | - / - / - | 0.66 |  |
| O03 | 1 1 1 | 1 1 1 | - / - / - | 1.00 |  |
| O04 | 1 1 1 | 1 1 1 | - / - / - | 1.00 |  |
| P01 | 0 0 0 | 0 0 0 | D01 D08 / D01 D08 / D01 D08 | 0.80 |  |
| P02 | 1 1 1 | 0 0 0 | D01 D10 D16 / D16 D20 / D10 D16 D20 | 0.54 | YES |
| P03 | 1 1 1 | 0 0 0 | D01 / D01 / D01 | 1.00 |  |
| P04 | 0 0 0 | 1 1 1 | - / - / - | 0.96 |  |
| P05 | 1 1 1 | 0 0 0 | D05 / D05 / D05 | 0.77 |  |
| P07 | 1 1 1 | 0 0 0 | D09 / D09 / D09 | 1.00 |  |
| P08 | 0 0 0 | 0 0 0 | D11 / D11 / D11 | 0.96 |  |
| P10 | 1 1 1 | 0 0 0 | D05 D10 / D05 D10 / D05 | 0.47 | YES |
| P12 | 1 1 1 | 0 0 0 | D16 / D16 / D16 | 0.94 |  |
| P13 | 1 1 1 | 0 0 0 | D29 / D29 / D29 | 1.00 |  |
| P14 | 1 1 1 | 0 0 0 | D18 D22 / D18 D22 / D18 D22 | 0.93 |  |
| P15 | 0 0 0 | 0 0 0 | D01 / D01 / D01 | 0.77 |  |
| P16 | 1 1 1 | 0 0 0 | D31 / D31 / D31 | 0.96 |  |
| P17 | 0 0 0 | 1 1 1 | - / - / - | 0.99 |  |
| S01 | 1 1 1 | 0 0 0 | D29 / D29 / D29 | 0.97 |  |
| S02 | 1 1 1 | 0 0 0 | D01 D11 D30 / D01 D11 D30 / D01 D11 D30 | 0.94 |  |
| S03 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 1.00 |  |
| S04 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 1.00 |  |
| S06 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 1.00 |  |
| S07 | 1 1 1 | 0 0 0 | D29 / D29 / D29 | 1.00 |  |
| S08 | 1 1 1 | 0 0 0 | - / - / - | 0.91 |  |

Questions whose outcome changed across runs: P02, P10
