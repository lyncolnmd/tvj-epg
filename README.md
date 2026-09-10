# TVJ IPTV + XMLTV Container

A configurable EPG engine that fetches channel schedules and serves a combined
XMLTV guide and M3U playlist over HTTP. TVJ, TVJ Sports Network, and Jamaica News Network share a Univtec
provider plugin; the engine fetches their common feed once per update.

## Run

Build this checkout and select both channels:

```sh
podman build -t tvj-epg .
podman run -d --name tvj-epg -p 1876:1876 \
  -e TZ=America/Jamaica \
  -e CHANNELS=tvj,tvjsn \
  -e UPDATE_INTERVAL=3 \
  tvj-epg
```

With no `CHANNELS` setting, only TVJ is included, preserving the default behavior.
Use `CHANNELS=tvjsn` for TVJ Sports Network alone.
Use `CHANNELS=tvj,tvjsn,jnn` to include Jamaica News Network as well, or
`CHANNELS=jnn` for JNN alone. JNN uses the same Univtec EPG feed and the supplied
stream URL `https://rjrjnn-ioriver-cdn.encoders.immergo.tv/2/streamPlaylist.m3u8`.

- Playlist: `http://localhost:1876/tvj.m3u`
- Guide: `http://localhost:1876/tvj.xml`

To use a different port, set `PORT` and match the container port in the mapping,
for example `-e PORT=8787 -p 8787:8787`. Recreating an existing container requires
updating its port mapping for the new default.

Both files contain the selected channels. Their XMLTV IDs and playlist `tvg-id`
values match automatically. Outputs become available after the first successful
update. Stream access is determined by the stream provider.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
| `PORT` | `1876` | HTTP listening port (1–65535) |
| `CHANNELS` | `tvj` | Comma-separated built-in channel keys; unknown keys fail startup |
| `UPDATE_INTERVAL` | `6` | Positive integer refresh interval in hours |
| `TZ` | Container timezone | Logging timezone; XMLTV timestamps remain UTC |
| `OUTPUT_FILE` | `/app/output/tvj.xml` | XMLTV output path |
| `M3U_OUTPUT_FILE` | `tvj.m3u` beside XMLTV output | Playlist output path |

The container serves `/app/output`; keep output paths there to expose the files
through its HTTP server.

| Channel key | Name | XMLTV / M3U ID |
| --- | --- | --- |
| `tvj` | Television Jamaica | `TVJ.jm@SD` |
| `tvjsn` | TVJ Sports Network | `TVJSN.jm@SD` |
| `jnn` | Jamaica News Network | `JNN.jm@SD` |

TVJ Sports Network uses the supplied video URL:
`https://vod2live.univtec.com/manifest/65cf631b-d422-49e0-ab25-07d5aa08ca8f/7660000.m3u8`.

## Architecture

- `epg/engine.py`: orchestrates configuration, shared fetching, and output.
- `epg/config.py`: built-in channel definitions and environment selection.
- `epg/models.py`: common channel and programme models.
- `epg/providers/`: provider adapters registered in `PROVIDERS`.
- `epg/writers.py`: XMLTV and M3U generation and atomic file replacement.
- `tvj_epj.py`: compatibility entry point for running the engine directly.

Add channels using an existing provider by adding a definition to `BUILTINS`.
A new provider adapter implements `fetch(url, tenant)` and
`programmes(data, channel_id)`, returning normalized `Programme` objects.
Optional enriched metadata is represented as XMLTV elements, preserving categories,
episode numbers, dates, durations, ratings, and artwork from the original script.
Univtec channel IDs select objects within the response; they are not URL suffixes.

All selected schedules must parse successfully before outputs are replaced.
A failed fetch or invalid schedule leaves previous files intact, and the container
retries at the next interval. Each file is replaced atomically; the two files are
not a single transaction. Old data can expire during prolonged outages.

Custom providers are out of scope for now. Per-channel cached fallback is not
implemented; a failed channel update preserves the previous combined outputs.
The root `tvj.m3u` is a legacy static example; container playlists are now generated.

## Local verification

With Python 3.11+ and `requests` installed:

```sh
python3 -m unittest discover -s tests -v
CHANNELS=tvj,tvjsn OUTPUT_FILE=output/tvj.xml python3 -m epg.engine
```

## Health reporting

`http://localhost:1876/health` returns JSON describing the latest scheduled
provider fetch, per-channel parsing results, current guide coverage, programme
counts, guide expiry, and XMLTV/M3U output validity. It uses the configured `PORT`.

| Status | HTTP code | Meaning |
| --- | --- | --- |
| `healthy` | 200 | Latest update succeeded, every selected channel covers now and has data extending into the future, and both outputs are usable |
| `degraded` | 200 | Outputs remain usable, but the latest update failed, no update record is available, or an update is overdue |
| `unhealthy` | 503 | At least one selected channel lacks current/future guide data, or a required output is missing or invalid |

An update is overdue after `UPDATE_INTERVAL` hours plus a five-minute grace period.
Startup without usable output reports unhealthy. Guide freshness is recalculated
on every health request, including during upstream outages. A current programme
whose end is in the future satisfies the future-data check; no minimum forecast
window is required. Schedule gaps report unhealthy while they are occurring.

The latest update result is stored atomically in `tvj.health.json` beside the
XMLTV output (the filename follows `OUTPUT_FILE`). This file is a stored update
record; `/health` computes live freshness and output checks. Provider status means
the last request and top-level response parsing succeeded; per-channel parsing
results are reported separately. Errors are identified by exception type.

The container checks `/health` every 30 seconds with a 60-second startup grace
period and three retries. Degraded status passes the container probe because the
existing outputs are still usable. These checks make no additional requests to
Univtec and do not check video-stream playback. Container health status alone does
not configure automatic restart behavior.

```sh
curl http://localhost:1876/health
podman inspect --format '{{.State.Health.Status}}' tvj-epg
```
