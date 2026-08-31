# LESSONS - auto-maintained by scripts/lessons.py

> Machine-owned. Do NOT hand-edit. Changes are overwritten on the next `lessons.py` write.
> Canonical state lives in `.specs/lessons.json`. Edit lessons only via the script.
> promote_threshold=2 distinct features · window_days=45 · quarantine_threshold=2

## Confirmed (load these at Specify/Design)

Corroborated across multiple features. Safe to apply as guidance.

_none_

## Candidates (under observation - do NOT load as guidance yet)

Seen once or not yet corroborated. Tracked, not trusted.

### L-001 - Pin composed-default wiring (which concrete transcriber/normalizer) with an end-to-end or intra-component assertion, not just mock.assert_called_once on the composed class.
- signal: `surviving_mutant` · recurrence: 1 feature(s) · scope: `app-layer;create_app-defaults` · harmful: 0
- features: nlp-pipeline
- evidence: server/x9ai/app.py:84 (mutant 6, validation.md) (app-layer;create_app-defaults)
- last seen: 2026-08-30T23:48:35Z

### L-002 - A create_app default-composition AC needs a test asserting the composed concrete components; mocking only the wrapper class leaves the default's real wiring unpinned.
- signal: `spec_precision_gap` · recurrence: 1 feature(s) · scope: `app-layer;create_app-defaults` · harmful: 0
- features: nlp-pipeline
- evidence: NLP-03, tests/test_real_pipeline.py:23 (validation.md) (app-layer;create_app-defaults)
- last seen: 2026-08-30T23:48:36Z

## Quarantined (failed when applied - ignore)

A confirmed lesson that recurred alongside failure. Kept for the maintainer to review.

_none_
