# Integration update

Implemented: durable local prototype queue; deterministic schedule planner; bounded local Blender/FFmpeg render smoke test; read-only dashboard; guarded YouTube upload adapter; offline mocked upload identity tests.

16 unit tests passed. Identity tests use mocks and are NOT a live Google OAuth check. No actual upload or live API credential validation has occurred in this update. Test suite also emitted SQLite resource warnings from test connection cleanup; production hardening remains required.

The new `studio.youtube_upload` module is separate from the intentionally blocked `core.publish` function. No caller connects it to the scheduler. It requires NOVA_ENABLE_UPLOAD=1 and OAuth secrets in process environment, validates duration/streams and review flags, verifies channels.list(mine=true) returns exactly the authorized channel, and writes a persistent artifact digest ledger before attempting public upload. Failures are marked uncertain and cannot be automatically retried. This is a first adapter, not production-ready: no chunk resumption, no automatic reconciliation, file memory limit 256 MiB, no deployed persistent ledger, and no enforcement of completed video quality beyond metadata flags and technical checks.

Outstanding: actual complete narrative generation pipeline, approved high-quality visual assets, professional audio design, bounded workers with heartbeats and monitoring, full rendered media QC, cost benchmarking, live OAuth check, production host, legacy run isolation, full integration and acceptance testing. No publishing workflow or permanent worker enabled. Branch must not be treated as a completed factory.

README revision 2 describes the earlier baseline. This update supersedes the claim that no upload adapter source exists; no operational publishing integration exists yet.
