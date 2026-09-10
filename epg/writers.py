"""Provider-independent output generation."""
import copy
import os
import tempfile
from datetime import timezone
from pathlib import Path
import xml.etree.ElementTree as ET


def xmltv(channels, schedules):
    root = ET.Element("tv", {"generator-info-name": "TVJ EPG Engine"})
    for channel in channels:
        node = ET.SubElement(root, "channel", id=channel.id)
        ET.SubElement(node, "display-name").text = channel.name
        if channel.icon:
            ET.SubElement(node, "icon", src=channel.icon)
    for channel in channels:
        for programme in schedules[channel.id]:
            node = ET.SubElement(root, "programme", channel=channel.id,
                start=programme.start.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S +0000"),
                stop=programme.stop.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S +0000"))
            ET.SubElement(node, "title", lang="en").text = programme.title
            ET.SubElement(node, "desc", lang="en").text = programme.description
            node.extend(copy.deepcopy(programme.metadata))
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def m3u(channels):
    lines = ["#EXTM3U"]
    for channel in channels:
        lines.extend([
            f'#EXTINF:-1 tvg-id="{channel.id}" tvg-name="{channel.name}" tvg-logo="{channel.icon}" group-title="{channel.group}",{channel.name}',
            channel.stream_url,
        ])
    return ("\n".join(lines) + "\n").encode("utf-8")


def atomic_write(path, content):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as output:
            temporary = output.name
            output.write(content)
            output.flush()
            os.fsync(output.fileno())
        os.chmod(temporary, 0o644)
        os.replace(temporary, path)
    finally:
        if temporary and os.path.exists(temporary):
            os.unlink(temporary)
