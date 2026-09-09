"""
Duplicate/conflict detection (\u00a718). Deliberately never blocks a sync or
registration -- a rejected sync just means the EXE silently has nowhere to
put real data. Instead, every conflict found here becomes a Notification
so an admin can review and resolve it, while the incoming data still gets
saved normally. This matches the rest of the system's core principle:
never silently discard data, always record + flag.
"""
PLACEHOLDER_VALUES = {
    '', 'unknown', 'not available', 'n/a', 'na', 'none', 'null',
    'to be filled by o.e.m.', 'to be filled by o.e.m',
    'system manufacturer', 'system product name', 'system version',
    'system serial number', 'default string', 'not specified',
}


def _is_real_value(value):
    """A blank or manufacturer-placeholder serial should never trigger a
    'duplicate' warning -- two devices both having an undetected CPU
    serial isn't a real conflict, it's just two undetected serials."""
    return bool(value) and value.strip().lower() not in PLACEHOLDER_VALUES


IDENTITY_SERIAL_FIELDS = {
    'cpu_serial': 'CPU Serial',
    'motherboard_serial': 'Motherboard Serial',
    'bios_serial': 'System/BIOS Serial',
    'monitor_serial': 'Monitor Serial',
}


def find_duplicate_serials(device, asset_data):
    """Checks the incoming asset_data (validated_data from the sync
    serializer, matching the real field names on Asset) against every
    OTHER active device's current Asset record. Returns a list of
    (field_label, serial_value, other_device) tuples -- empty if no
    conflicts. A modest device count (tens, not thousands) makes a
    straightforward Python-side scan simpler and more robust here than a
    fragile JSON containment query, particularly for the per-drive
    storage_devices list."""
    from core.models import Asset  # local import avoids a circular import with models.py

    conflicts = []
    other_assets = Asset.objects.exclude(device=device).exclude(device__is_active=False) \
        .select_related('device')

    for field, label in IDENTITY_SERIAL_FIELDS.items():
        value = (asset_data.get(field) or '').strip()
        if not _is_real_value(value):
            continue
        match = other_assets.filter(**{field: value}).first()
        if match:
            conflicts.append((label, value, match.device))

    incoming_storage = asset_data.get('storage_devices') or []
    incoming_serials = {(d.get('serial') or '').strip() for d in incoming_storage if isinstance(d, dict)}
    incoming_serials = {s for s in incoming_serials if _is_real_value(s)}
    if incoming_serials:
        for other_asset in other_assets:
            for drive in (other_asset.storage_devices or []):
                if not isinstance(drive, dict):
                    continue
                other_serial = (drive.get('serial') or '').strip()
                if other_serial in incoming_serials:
                    conflicts.append((f"Storage Drive Serial ({drive.get('model', '?')})",
                                       other_serial, other_asset.device))

    return conflicts


def notify_duplicate_serials_if_new(device, conflicts):
    """Creates a Notification for each conflict found -- but only if an
    unread notification for this exact device+field+other-device
    combination doesn't already exist, so a device that keeps syncing
    with the same unresolved conflict doesn't spam a new notification
    every few minutes."""
    from core.models import Notification  # local import avoids a circular import with models.py

    for label, value, other_device in conflicts:
        message = (f"{label} \u2018{value}\u2019 on {device.hostname} is already assigned to "
                   f"{other_device.hostname}.")
        already_flagged = Notification.objects.filter(
            type='duplicate_asset', device=device, message=message, is_read=False).exists()
        if not already_flagged:
            Notification.objects.create(
                type='duplicate_asset', severity='warning', message=message,
                device=device, branch=device.branch,
            )


def notify_if_employee_has_multiple_active_devices(employee):
    """\u00a718: multiple active devices per employee is NOT an error --
    some organizations legitimately do this -- but it should be visible
    to an admin rather than silent. Only fires once per employee while
    unresolved (same de-duplication approach as duplicate serials)."""
    from core.models import DeviceAssignment, Notification  # local import avoids circularity

    if employee is None:
        return
    active_count = DeviceAssignment.objects.filter(employee=employee, is_active=True).count()
    if active_count < 2:
        return
    message = f"{employee.name} currently has {active_count} active devices assigned."
    already_flagged = Notification.objects.filter(
        type='multiple_devices', message=message, is_read=False).exists()
    if not already_flagged:
        Notification.objects.create(
            type='multiple_devices', severity='info', message=message,
            branch=employee.branch,
        )
