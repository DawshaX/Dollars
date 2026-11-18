# Queue-to-render integration

## Run a bounded real smoke job

From nova_studio/ with Python 3, Blender, FFmpeg and FFprobe installed:

    python -m unittest discover -s tests -v
    python -m studio.render_worker --seed-test --max-jobs 1

This is a real pipeline: SQLite claim -> periodic lease heartbeat -> Blender render -> procedural audio -> FFmpeg encode -> FFprobe checks -> full media decode -> artifact copy -> review state.

Artifacts are in render_jobs/<job-id>/:
- brief.json
- events.jsonl
- build.log
- preview.mp4
- quality.json

A cross-process flock serializes the renderer because the current recipe has shared intermediate paths. Jobs are bounded, with a 1500-second build timeout. Review flags remain false. Unknown production recipes fail closed. No upload adapter is invoked.

## Important limitations
This integrates the technical four-second engine test, NOT a production storytelling recipe. No finished narrative short or 5–20 minute film has been produced. No permanent daemon, live credential test, YouTube upload or production deployment is implied. Do not multiply this test into a long video or present it as the approved cinematic content.

The user-authorized target cadence remains a short every four hours (1–180 seconds) and a long video every five hours (300–1200 seconds). schedule.py plans slots; slots do not yet create approved production recipes. The worker deliberately refuses arbitrary recipes rather than publishing placeholder content.
