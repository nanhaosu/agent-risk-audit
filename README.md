# Agent Risk Audit

Reproducible offline tooling for auditing ordinal risk-rating records from language-model agents.

**Status: ongoing research; first public engineering artifact.** This release demonstrates record preservation, conservative statistical admission, and isolated interoperability with a pinned Judge Reliability Harness (JRH) cache reader. It does not establish a new scoring method, benchmark improvement, competition ranking, or completed independent human validation.

[中文概览](README.zh-CN.md) · [Evidence](docs/EVIDENCE.md) · [Runbook](docs/JRH_OFFLINE_RUNBOOK.md)

## What you can reproduce

- Preserve source, condition, repeat, prompt hash, original response and provenance.
- Keep failures, missing slots, unexpected records and duplicate attempts visible.
- Recheck raw responses and planned metadata; exclude all responses from duplicated slots.
- Read indexed CSV results through an unmodified, pinned JRH cache branch with scoring and socket entry points blocked.
- Count admitted records separately by source and condition.

The fixture contains **10 synthetic records: 1 admitted, 9 excluded**. Eleven unit tests and four deliberate scoring/network probes are executable locally. No API key, hosted model, GPU or private dataset is required.

## Quick start

Use Python 3.12 or 3.13. Prepare dependencies separately; installation requires a package index or pre-provisioned wheel cache. The checks themselves operate offline.

```bash
python -m venv .venv
# Activate .venv using your operating system's standard command.
python -m pip install -r requirements.txt
python run_checks.py
python scripts/jrh_offline.py --bundle fixture --output my-results
```

Expected: 11 unit tests, 10 records, 1 eligible, 9 excluded, 4 blocked probes, 0 model API calls. Use a fresh output directory for the CLI.

Outputs: all-records.jsonl, eligible-records.jsonl, excluded-records.jsonl, summary.json and an indexed cache CSV. **The cache contains every record, including failures; it is not the admitted sample table.**

## Research question

The broader project studies whether target-linkage certainty moderates the effect of equivalent input representations on ordinal agent-action risk ratings, while checking authorization and other risk conditions. Identity, linkage, permission and overall safety are distinct judgments. This release supplies engineering controls; it does not validate the hypothesis.

Next gates are independent semantic review, reanalysis against reviewer judgments, and frozen validation on new source scenarios. Repeated calls do not increase the number of independent sources.

## Attribution and limits

JRH already covers generic judge reliability testing, human review, and agent/ordinal tasks. We do not claim those capabilities as novel. vendor/jrh/evaluator.py is copied without modification from [RAND Judge Reliability Harness](https://github.com/RANDCorporation/judge-reliability-harness), commit 82ef3aed74950ba03eadcdb087743251196355a3; its MIT license is retained. See [third-party notices](THIRD_PARTY_NOTICES.md).

Our wrapper replaces SDK/config import seams with inert stand-ins and blocks scoring methods. This is an isolated cache-reader check, not a full JRH installation or paper reproduction. Python guards are not an OS sandbox for arbitrary code. The full upstream project declares Python >=3.13; our isolated reader was tested locally on Python 3.12.14.

Only synthetic fixtures are published. No research trajectories, patient or wallet examples, credentials, reviewer answers or historical model responses are included. A manifest detects file changes; it is not a digital signature. Admission demonstrates record integrity, not semantic correctness or a gold risk label.

## License

Project code: MIT. Upstream copyright remains with RAND for the vendored file. Maintainer: [Nanhao SU](https://github.com/nanhaosu).
