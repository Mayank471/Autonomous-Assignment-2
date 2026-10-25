# Evaluation summary (qwen3-8b)

## single-agent (3 runs x 30 questions)

| Metric | Value |
|---|---|
| Accuracy, answerable questions | 74% (51/69) |
| Accuracy, answerable questions (automatic key-fact check only) | 78% (54/69) |
| Items manually graded | 90/90 |
| Groundedness, cited doc matches source | 84% (58/69) |
| Groundedness, cited doc+page matches | 80% (55/69) |
| Retrieval hit (expected source returned by a tool) | 84% (58/69) |
| Correct refusal, out-of-scope (refused and logged) | 100% (12/12) |
| Out-of-scope refused (ignoring logging) | 100% (12/12) |
| Correct 'no data' handling (assignment items without public data) | 67% (6/9) |
| False refusals on answerable questions | 16% (11/69) |
| Answers containing a fabricated URL (all questions) | 0% (0/90) |
| Median latency | 36 s |
| Errors | 0 |

| Category | Accuracy |
|---|---|
| policy | 67% (30/45) |
| schedule | 67% (12/18) |
| email | 100% (15/15) |
| out_of_scope | 100% (12/12) |

### Run-to-run consistency

| Question | Correct per run | Refused per run | Cited docs per run | Answer similarity | Changed |
|---|---|---|---|---|---|
| E01 | 1 1 1 | 1 1 1 | - / - / - | 0.40 |  |
| E02 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.97 |  |
| E03 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.98 |  |
| E04 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.95 |  |
| E05 | 1 1 1 | 0 0 0 | D28-computer-science-engineering / D28-computer-science-engineering / D28-computer-science-engineering | 0.99 |  |
| O01 | 1 1 1 | 1 1 1 | - / - / - | 0.60 |  |
| O02 | 1 1 1 | 1 1 1 | - / - / - | 0.58 |  |
| O03 | 1 1 1 | 1 1 1 | - / - / - | 0.75 |  |
| O04 | 1 1 1 | 1 1 1 | - / - / - | 0.55 |  |
| P01 | 0 0 0 | 0 0 0 | D01 D08 / D01 D08 / D01 D08 | 0.82 |  |
| P02 | 1 0 1 | 0 0 0 | D01 D16 D20 / D01 D10 / D01 D16 D20 | 0.47 | YES |
| P03 | 1 1 1 | 0 0 0 | D01 / D01 D05 / D01 D05 | 0.60 | YES |
| P04 | 1 1 1 | 0 0 0 | D01 D05 / D01 D05 / D01 D05 | 0.94 |  |
| P05 | 1 1 1 | 0 0 0 | D01 D05 / D01 D05 / D05 | 0.58 | YES |
| P06 | 0 1 0 | 1 0 1 | - / D08 / - | 0.34 | YES |
| P07 | 1 1 1 | 0 0 0 | D09 / D09 / D09 | 1.00 |  |
| P08 | 0 0 0 | 0 0 0 | D11 / D11 / D11 | 0.97 |  |
| P09 | 1 1 1 | 0 0 0 | D11 / D11 / D11 | 1.00 |  |
| P10 | 1 1 1 | 0 0 0 | D01 D05 / D05 / D01 D05 | 0.67 | YES |
| P11 | 1 1 1 | 0 0 0 | D01 / D01 / D01 | 1.00 |  |
| P12 | 1 1 1 | 0 0 0 | D16 / D16 / D16 | 0.90 |  |
| P13 | 0 0 0 | 1 1 1 | - / - / - | 0.58 |  |
| P14 | 0 0 0 | 1 1 1 | - / - / - | 0.78 |  |
| P15 | 1 1 1 | 0 0 0 | D01 / D01 / D01 | 0.63 |  |
| S01 | 1 1 1 | 0 0 0 | D11 / D11 / - | 0.81 | YES |
| S02 | 0 0 0 | 0 0 0 | D01 / D01 / D01 | 0.98 |  |
| S03 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.99 |  |
| S04 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.78 |  |
| S05 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.88 |  |
| S06 | 0 0 0 | 1 1 1 | - / - / - | 0.68 |  |

Questions whose outcome changed across runs: P02, P03, P05, P06, P10, S01

## multi-agent (3 runs x 30 questions)

| Metric | Value |
|---|---|
| Accuracy, answerable questions | 75% (52/69) |
| Accuracy, answerable questions (automatic key-fact check only) | 75% (52/69) |
| Items manually graded | 90/90 |
| Groundedness, cited doc matches source | 81% (56/69) |
| Groundedness, cited doc+page matches | 78% (54/69) |
| Retrieval hit (expected source returned by a tool) | 81% (56/69) |
| Correct refusal, out-of-scope (refused and logged) | 100% (12/12) |
| Out-of-scope refused (ignoring logging) | 100% (12/12) |
| Correct 'no data' handling (assignment items without public data) | 67% (6/9) |
| False refusals on answerable questions | 14% (10/69) |
| Answers containing a fabricated URL (all questions) | 3% (3/90) |
| Routing accuracy | 93% (84/90) |
| Median latency | 36 s |
| Errors | 0 |

| Category | Accuracy |
|---|---|
| policy | 76% (34/45) |
| schedule | 67% (12/18) |
| email | 80% (12/15) |
| out_of_scope | 100% (12/12) |

### Run-to-run consistency

| Question | Correct per run | Refused per run | Cited docs per run | Answer similarity | Changed |
|---|---|---|---|---|---|
| E01 | 1 1 1 | 1 1 1 | - / - / - | 0.86 |  |
| E02 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.74 |  |
| E03 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.97 |  |
| E04 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.73 |  |
| E05 | 0 0 0 | 1 1 1 | - / - / - | 0.77 |  |
| O01 | 1 1 1 | 1 1 1 | - / - / - | 0.83 |  |
| O02 | 1 1 1 | 1 1 1 | - / - / - | 1.00 |  |
| O03 | 1 1 1 | 1 1 1 | - / - / - | 1.00 |  |
| O04 | 1 1 1 | 1 1 1 | - / - / - | 1.00 |  |
| P01 | 1 1 1 | 0 0 0 | D08 / D01 D08 / D01 D08 | 0.79 | YES |
| P02 | 1 1 1 | 0 0 0 | D16 / D01 / D01 | 0.44 | YES |
| P03 | 1 1 1 | 0 0 0 | D01 / D01 / D01 | 0.95 |  |
| P04 | 0 0 0 | 1 1 1 | - / - / - | 0.75 |  |
| P05 | 1 1 1 | 0 0 0 | D05 / D05 / D05 | 0.66 |  |
| P06 | 1 1 1 | 0 0 0 | D08 / D08 / D08 | 1.00 |  |
| P07 | 1 1 1 | 0 0 0 | D09 / D09 / D09 | 1.00 |  |
| P08 | 0 0 1 | 0 0 0 | D11 / D11 / D11 | 0.94 | YES |
| P09 | 1 1 1 | 0 0 0 | D11 / D11 / D11 | 0.89 |  |
| P10 | 1 1 1 | 0 0 0 | D05 D10 / D05 D10 / D05 D10 | 1.00 |  |
| P11 | 1 1 1 | 0 0 0 | D01 / D01 / D01 | 0.99 |  |
| P12 | 1 1 1 | 0 0 0 | D16 / D16 / D16 | 0.97 |  |
| P13 | 0 0 0 | 0 0 0 | - / - / - | 0.74 |  |
| P14 | 1 1 1 | 0 0 0 | D18 D22 / D18 D22 / D18 D22 | 0.96 |  |
| P15 | 0 0 0 | 0 1 0 | D01 / - / D01 | 0.35 | YES |
| S01 | 1 1 1 | 1 1 1 | - / - / - | 0.85 |  |
| S02 | 0 0 0 | 0 0 0 | D01 / D01 / D01 | 1.00 |  |
| S03 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.99 |  |
| S04 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.98 |  |
| S05 | 1 1 1 | 0 0 0 | D15 / D15 / D15 | 0.94 |  |
| S06 | 0 0 0 | 1 1 1 | - / - / - | 0.78 |  |

Questions whose outcome changed across runs: P01, P02, P08, P15
