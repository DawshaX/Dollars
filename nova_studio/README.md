# NOVA 2099 — local engineering prototype, revision 2

Target repository: DawshaX/Dollars only.
Target channel: UCG9g_26H65D3FahqyiYPHAw (xDaw NoVa).

## Actual status
This code is local, NOT committed to GitHub or deployed as a permanent factory. No YouTube upload adapter is active. No publishing or other repository changes were made in this build. Publishing deliberately raises an error.

Installed free system tools: Blender 4.3.2 and FFmpeg. The environment initially lacked them; installation has now completed. These installed tools and running services may not survive a new sandbox session; source and deliverables under /home/user are saved subject to platform limits.

## Implemented and tested
- SQLite durable job queue, fingerprint uniqueness, transactional claim, five-minute leases, expired-lease recovery, maximum three claims.
- Basic event log, preproduction brief generation, channel guard and review metadata validation.
- Six passing unit tests. These are NOT proof of production readiness or real visual/audio/rights verification.
- A locally rendered 4-second vertical 3D test, 360x640 at 12 fps, with synthesized tone audio. FFprobe verified audio/video streams and 4-second duration.
- Read-only dashboard, successfully tested for HTML and video delivery.

## Preview
`renders/NOVA_ENGINE_TEST.mp4` is a technical smoke test, NOT a finished cinematic pilot. The scene contains simple animated stylized forms, lighting and camera motion. It is low resolution with visible sampling noise; no finished character, story, photorealism, or professional sound mix is claimed.
`renders/nova_preview.blend` is the saved scene used in rendering.
`renders/validation.json` contains technical results, not publication approval. One final frame was inspected by the assistant; full editorial human review is still pending.

## Commands
Python 3 standard library is sufficient for queue and dashboard:

    python -m unittest discover -s tests -v
    python -m studio seed
    python -m studio step
    python -m studio status
    python -m studio.dashboard

Dashboard binds to 0.0.0.0:8080 and is read-only. It is a sandbox demo without authentication, NOT an admin console for public production deployment. It does not start jobs or publish.

To install render tools on a compatible Debian system (requires administrator approval):

    sudo apt-get update
    sudo apt-get install blender ffmpeg

Render the smoke test, synthesize audio, assemble and validate:

    python -m studio.build_preview

This uses CPU and has a 20-minute render timeout. Cycles denoising is disabled because this installed Blender build lacks OpenImageDenoise support. For better production quality, evaluate higher samples, supported denoising, resolution and compute cost.

`scenes/glass_garden.py` is a separate earlier, untested project-generation draft. The executed preview is `scenes/render_preview.py`.

## Still required
- Integrate via isolated branch/PR in Dollars without enabling legacy workflows. No remote integration has occurred.
- Replace exposed GitHub credential using secure credentials management. No credentials are bundled.
- Bounded nonpublishing API health tests using GitHub Secrets without exporting values.
- Approved character/world/style guide, storyboard, animatic and a real narrative pilot with designed sound.
- Durable render workers, heartbeat, cancellation, retry backoff, budgets, storage cleanup, monitoring and backups. Current leases are insufficient for long renders without heartbeat. The queue and renderer are NOT yet one automated end-to-end pipeline.
- Rights checks, duplicate-content checks and actual image/audio analysis. Review flags alone are not these checks.
- YouTube OAuth identity verification via channels.list, idempotent upload reconciliation and approval control before enabling a publisher.
- Neutralize pending legacy jobs before enabling any Actions.
- Provision a durable host for ongoing operation. No unlimited free hosting, rendering, APIs or views are promised. No paid services have been purchased.

No automatic continuous production worker is running. Only a temporary read-only preview server was started. No actual posting schedule has been created or enabled.
