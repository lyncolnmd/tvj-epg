"""Built-in channels and environment configuration."""
import os
from pathlib import Path
from epg.models import Channel

BUILTINS = {
    "tvj": Channel(
        id="TVJ.jm@SD", name="Television Jamaica",
        channel_id="66e312890478fd00235244cb",
        stream_url="https://vod2live.univtec.com/manifest/a99a1804-dc83-411f-8c1c-b62f08cdfa59.m3u8",
        icon="https://rjr.vod.immergo.tv/rjr/uploaded/abeb1489-7346-4e0f-b9c4-b351e2a47fb0.png",
    ),
    "tvjsn": Channel(
        id="TVJSN.jm@SD", name="TVJ Sports Network",
        channel_id="66e4618e42b97c0024de5231",
        stream_url="https://vod2live.univtec.com/manifest/65cf631b-d422-49e0-ab25-07d5aa08ca8f/7660000.m3u8",
        icon="https://rjr.vod.immergo.tv/rjr/uploaded/85c62d19-8e57-49b5-820a-acca5adcc1c9.png",
        group="Sports",
    ),
}


def load(environ=None):
    env = os.environ if environ is None else environ
    keys = list(dict.fromkeys(k.strip().lower() for k in env.get("CHANNELS", "tvj").split(",") if k.strip()))
    if not keys:
        raise ValueError("CHANNELS must select at least one channel")
    unknown = set(keys) - BUILTINS.keys()
    if unknown:
        raise ValueError(f"Unknown CHANNELS: {', '.join(sorted(unknown))}; available: {', '.join(BUILTINS)}")
    xml_path = Path(env.get("OUTPUT_FILE", "/app/output/tvj.xml"))
    m3u_path = Path(env.get("M3U_OUTPUT_FILE", str(xml_path.with_name("tvj.m3u"))))
    if xml_path.resolve() == m3u_path.resolve():
        raise ValueError("OUTPUT_FILE and M3U_OUTPUT_FILE must be different")
    return [BUILTINS[k] for k in keys], xml_path, m3u_path
