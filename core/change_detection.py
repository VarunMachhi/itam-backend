"""
Compares an incoming hardware scan (from the client EXE) against the
previously stored Asset snapshot and returns a list of changes to be
written to AssetChangeLog. Nothing here writes to the database directly
-- the caller (views.py) decides how to persist the result, which keeps
this module easy to unit test in isolation.
"""
from core.models import Asset


def _norm(value):
    """Treat None, '', 'Unknown' and 'Not Available' as equivalent
    'nothing detected' states so we don't log noisy false-positive
    changes between those placeholder values."""
    if value in (None, '', 'Unknown', 'Not Available'):
        return ''
    return str(value).strip()


def diff_scalar_fields(old_snapshot: dict, new_scan: dict):
    """old_snapshot / new_scan: plain dicts of Asset field name -> value.
    Returns a list of dicts: {field_name, change_type, old_value, new_value}."""
    changes = []
    for field in Asset.SCALAR_TRACKED_FIELDS:
        old_val = _norm(old_snapshot.get(field))
        new_val = _norm(new_scan.get(field))
        if old_val == new_val:
            continue

        if not old_val and new_val:
            change_type = 'Added'
        elif old_val and not new_val:
            change_type = 'Removed'
        else:
            change_type = 'Updated'

        changes.append({
            'field_name': field,
            'change_type': change_type,
            'old_value': old_val,
            'new_value': new_val,
        })
    return changes


def diff_component_list(old_list, new_list, field_label, serial_key='serial', desc_keys=('size', 'manufacturer')):
    """Diffs a list of component dicts (RAM sticks or storage drives) by
    serial number. Returns change dicts for each addition/removal, and a
    'Replaced' entry when the count stays the same but the set of serials
    changed (the common real-world case: one stick/drive swapped for
    another)."""
    old_list = old_list or []
    new_list = new_list or []

    def describe(item):
        return ', '.join(str(item.get(k)) for k in desc_keys if item.get(k)) or 'unknown component'

    old_by_serial = {i.get(serial_key): i for i in old_list if _norm(i.get(serial_key))}
    new_by_serial = {i.get(serial_key): i for i in new_list if _norm(i.get(serial_key))}

    old_serials = set(old_by_serial)
    new_serials = set(new_by_serial)

    removed = old_serials - new_serials
    added = new_serials - old_serials

    changes = []

    # Pair up one removed + one added as "Replaced" where possible (more
    # useful for an IT audit than two separate Added/Removed rows), then
    # log any leftovers individually.
    removed_list = list(removed)
    added_list = list(added)
    for old_serial, new_serial in zip(removed_list, added_list):
        changes.append({
            'field_name': field_label,
            'change_type': 'Replaced',
            'old_value': f"{describe(old_by_serial[old_serial])} (SN: {old_serial})",
            'new_value': f"{describe(new_by_serial[new_serial])} (SN: {new_serial})",
        })

    leftover_removed = removed_list[len(added_list):]
    leftover_added = added_list[len(removed_list):]

    for old_serial in leftover_removed:
        changes.append({
            'field_name': field_label,
            'change_type': 'Removed',
            'old_value': f"{describe(old_by_serial[old_serial])} (SN: {old_serial})",
            'new_value': '',
        })
    for new_serial in leftover_added:
        changes.append({
            'field_name': field_label,
            'change_type': 'Added',
            'old_value': '',
            'new_value': f"{describe(new_by_serial[new_serial])} (SN: {new_serial})",
        })

    return changes


def diff_asset(existing_asset: 'Asset | None', new_scan: dict):
    """Top-level entry point used by the sync view.
    existing_asset: the current Asset row for this device, or None on
    first-ever registration (in which case everything is 'Added', but we
    intentionally don't log a wall of Added rows for a brand-new device
    -- see views.py, which skips change-logging entirely on first sync)."""
    old_snapshot = {}
    old_ram, old_storage = [], []
    if existing_asset is not None:
        old_snapshot = {f: getattr(existing_asset, f) for f in Asset.SCALAR_TRACKED_FIELDS}
        old_ram = existing_asset.ram_devices or []
        old_storage = existing_asset.storage_devices or []

    changes = diff_scalar_fields(old_snapshot, new_scan)
    changes += diff_component_list(old_ram, new_scan.get('ram_devices', []), 'ram_devices',
                                    desc_keys=('size', 'manufacturer'))
    changes += diff_component_list(old_storage, new_scan.get('storage_devices', []), 'storage_devices',
                                    desc_keys=('size', 'type', 'name'))
    return changes
