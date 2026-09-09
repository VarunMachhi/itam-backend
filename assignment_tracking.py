"""
Automatic assignment-history tracking. Device.employee/Device.branch only
ever hold the CURRENT assignment; this is what gives that a memory --
whenever a sync or registration detects the assignment actually changed
(not just re-confirmed the same one), it closes out whatever was
previously active and opens a new DeviceAssignment row.

Deliberately a no-op if nothing actually changed, so a device syncing
with the same employee/branch every day doesn't create a new row each
time -- only real transfers/reassignments get recorded.
"""
from django.utils import timezone


def record_assignment_if_changed(device, employee, branch, assignment_type='primary', notes=''):
    """Call after device.employee / device.branch have been updated in
    memory but BEFORE (or after -- order doesn't matter, this reads the
    values passed in, not the DB) device.save(). Safe to call on every
    sync/registration; it only writes anything when the assignment is
    actually different from whatever's currently active."""
    from core.models import DeviceAssignment  # local import avoids a circular import with models.py

    current = DeviceAssignment.objects.filter(device=device, is_active=True).first()
    if current and current.employee_id == (employee.id if employee else None) \
            and current.branch_id == (branch.id if branch else None):
        return  # unchanged -- nothing to record

    now = timezone.now()
    if current:
        current.is_active = False
        current.unassigned_at = now
        current.save(update_fields=['is_active', 'unassigned_at'])

    if employee or branch:
        DeviceAssignment.objects.create(
            device=device, employee=employee, branch=branch,
            assignment_type=assignment_type, is_active=True, notes=notes,
        )
