# TVJ IPTV + XMLTV Container

This project provides a **self-contained IPTV helper container** that:

* Serves a **TVJ M3U playlist** (stream data)
* Automatically fetches and updates **XMLTV EPG data** for Television Jamaica (TVJ)
* Hosts both files over HTTP for easy consumption by IPTV clients

The container is designed to run unattended and continuously refresh the EPG on a schedule.

---

## What this container provides

When deployed, the container exposes the following URLs:

* **Playlist (M3U):**  
  `http://localhost:8787/tvj.m3u`

* **EPG (XMLTV):**  
  `http://localhost:8787/tvj.xml`

These can be used directly in:

* Plex
* Jellyfin
* Kodi
* Tivimate
* TVHeadend
* Any XMLTV / M3U compatible IPTV client

The playlist and EPG are matched using:

```
tvg-id="TVJ.jm@SD"
```
---

### Run the container

```bash
podman run -d \
  --name tvj-epg \
  -p 8787:8787 \
  -e TZ=America/Jamaica \
  -e UPDATE_INTERVAL=3 \
    ghcr.io/lyncolnmd/tvj-epg:latest
```

#### Environment variables

| Variable          | Description                                            |
| ----------------- | ------------------------------------------------------ |
| `TZ`              | Timezone used **for logging only** (XMLTV remains UTC) |
| `UPDATE_INTERVAL` | How often the EPG is refreshed (hours)                 |

---

## IPTV client configuration

### Playlist URL

```
http://localhost:8787/tvj.m3u
```

### EPG URL

```
http://localhost:8787/tvj.xml
```

Most clients will automatically match the guide using the `tvg-id`.

---

## Logging and updates

Container logs show:

* When the script last ran
* When the XML file was written
* How far into the future the EPG data extends

Example:

```
[2026-02-01 10:46:11 EST] Script run started (TZ=America/Jamaica)
[2026-02-01 10:46:11 EST] XMLTV written: /app/output/tvj.xml
Summary: Last run=2026-02-01 10:46:11 EST, EPG updated until=2026-02-02 10:34:04 EST
```

---

## Updating the container

The container image is built automatically via **GitHub Actions**.


