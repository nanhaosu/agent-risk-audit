# Offline workflow

Run `python run_checks.py` for repeatable temporary verification, or `python scripts/jrh_offline.py --bundle fixture --output my-results` to keep outputs. The latter requires a new destination.

Input hashes, CSV/JSONL agreement, planned-slot coverage and pinned source hashes are checked. The cache branch has fixed configuration: no model, test-name, overwrite or resume-scoring option is exposed. SDK imports are replaced; scoring paths and socket connections raise errors.

Admission requires a planned slot, matching source/condition/representation/hash, an unambiguous response, status ok, an integer grade in 1..5 and strict parsing of the original response. All responses in duplicate slots are excluded. Unknown or failed records remain visible with exclusion reasons.

summary.json counts admitted records by source and condition. It does not infer gold labels or run JRH metrics. Repeats are not independent scenarios; admission does not imply human validation.

The full indexed cache retains exceptions: JRH treats existing IDs as processed regardless of status. Never use that cache as the valid-sample denominator. JSONL preserves raw synthetic response content; CSV offers scalar interoperability.

For other data, supply a separately audited export bundle. This release is validated on its supplied synthetic fixture and documented local checks. It does not automate data publication or permissions.
