# TVJ IPTV + XMLTV Container

A configurable EPG engine that fetches channel schedules and serves a combined
XMLTV guide and M3U playlist over HTTP. TVJ and TVJ Sports Network share a Univtec
provider plugin; the engine fetches their common feed once per update.

## Run

Build this checkout and select both channels:

```sh
podman build -t tvj-epg .
podman run -d --name tvj-epg -p 8787:8787 \
  -e TZ=America/Jamaica \
  -e CHANNELS=tvj,tvjsn \
  -e UPDATE_INTERVAL=3 \
  tvj-epg
```

With no `CHANNELS` setting, only TVJ is included, preserving the default behavior.
Use `CHANNELS=tvjsn` for TVJ Sports Network alone.

- Playlist: `http://localhost:8787/tvj.m3u`
- Guide: `http://localhost:8787/tvj.xml`

Both files contain the selected channels. Their XMLTV IDs and playlist `tvg-id`
values match automatically. Outputs become available after the first successful
update. Stream access is determined by the stream provider.

## Configuration

| Variable | Default | Meaning |
| --- | --- | --- |
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

Custom feed/channel environment settings, per-channel cached fallback, and health
reporting are planned for subsequent milestones; they are not implemented yet.
The root `tvj.m3u` is a legacy static example; container playlists are now generated.

## Local verification

With Python 3.11+ and `requests` installed:

```sh
python3 -m unittest discover -s tests -v
CHANNELS=tvj,tvjsn OUTPUT_FILE=output/tvj.xml python3 -m epg.engine
```
