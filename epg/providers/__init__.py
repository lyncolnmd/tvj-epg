"""Provider plugins implement fetch(url, tenant) and programmes(data, channel_id)."""
from epg.providers import univtec

PROVIDERS = {"univtec": univtec}
