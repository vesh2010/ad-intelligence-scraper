from __future__ import annotations
from collections import defaultdict
from typing import Any

def _norm(value: Any) -> str:
    return str(value or '').strip().lower().rstrip('/')

def compare_devices(observations: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(lambda: {'desktop': [], 'mobile': []})
    for row in observations:
        key = _norm(row.get('campaign_key')) or _norm(row.get('ad_id'))
        device = _norm(row.get('device'))
        if key and device in {'desktop', 'mobile'}:
            groups[key][device].append(row)
    rows=[]
    for key, group in groups.items():
        d,m=group['desktop'],group['mobile']
        dp=sorted({_norm(r.get('ad_unit_code')) for r in d if _norm(r.get('ad_unit_code'))})
        mp=sorted({_norm(r.get('ad_unit_code')) for r in m if _norm(r.get('ad_unit_code'))})
        rows.append({'campaign_key':key,'desktop_observations':len(d),'mobile_observations':len(m),'desktop_only':bool(d) and not m,'mobile_only':bool(m) and not d,'both_devices':bool(d) and bool(m),'desktop_placements':dp,'mobile_placements':mp,'shared_placements':sorted(set(dp)&set(mp))})
    rows.sort(key=lambda r:(-int(r['both_devices']),-(r['desktop_observations']+r['mobile_observations']),r['campaign_key']))
    return {'campaigns':rows,'campaign_count':len(rows),'both_device_campaigns':sum(r['both_devices'] for r in rows),'desktop_only_campaigns':sum(r['desktop_only'] for r in rows),'mobile_only_campaigns':sum(r['mobile_only'] for r in rows)}
