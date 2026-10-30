# Benchmarks

Results from running the skill's eval cases with the skill (`with_skill`) and without any
skill (`without_skill`, a baseline), in the format produced by Anthropic's skill-creator.

| Iteration | Cases | Runs | With skill | Without skill | Notes |
|---|---|---|---|---|---|
| [iteration-1](iteration-1/benchmark.md) | `ts-service-local-checkout` | 1 per config | 8/8 (353s, 124k tokens) | 6/8 (450s, 115k tokens) | Directional only; see the notes in `benchmark.json` |

Each case folder holds:

- `eval_metadata.json`: the prompt and the assertions
- `<config>/outputs/`: what the run produced. `final_response.md` is the chat reply; the guide is the deliverable
- `<config>/grading.json`: pass/fail with evidence for each assertion
- `<config>/timing.json`: tokens and wall-clock time

The repo checkouts each run worked in aren't included. To recreate one, run
`evals/<case>/place-files.sh` in an empty directory.
