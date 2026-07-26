"""
Core data models for the cloud Asset Management backend.

Design notes:
- Device is the central identity: one row per installed client (per PC).
  It carries its own API key (§11 security requirement: unique device
  registration + authenticated API access).
- Asset is a *current snapshot* of that device's hardware, one-to-one
  with Device -- overwritten on every sync.
- AssetChangeLog is the permanent audit trail (§5): every detected field
  change is appended here and never overwritten, so history survives
  even though Asset itself only holds the latest snapshot.
"""
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


def generate_api_key():
    return secrets.token_urlsafe(32)


class Branch(models.Model):
    name = models.CharField(max_length=120, unique=True)
    address = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Employee(models.Model):
    name = models.CharField(max_length=120)
    designation = models.CharField(max_length=120, blank=True)
    department = models.CharField(max_length=120, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='employees')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class Device(models.Model):
    """One row per installed Employee Asset EXE. This is the thing that
    authenticates and syncs -- not the employee, since a device can be
    reassigned between employees over its lifetime while keeping its own
    continuous identity and history."""

    DEVICE_TYPE_CHOICES = [
        ('Laptop', 'Laptop'),
        ('Desktop', 'Desktop'),
        ('Unknown', 'Unknown'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    api_key = models.CharField(max_length=64, unique=True, default=generate_api_key, editable=False)

    hostname = models.CharField(max_length=120)
    mac_address = models.CharField(max_length=32, blank=True, db_index=True)
    ip_address = models.CharField(max_length=64, blank=True)
    os_info = models.CharField(max_length=120, blank=True)
    device_type = models.CharField(max_length=10, choices=DEVICE_TYPE_CHOICES, default='Unknown')

    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='devices')
    employee = models.ForeignKey(Employee, on_delete=models.SET_NULL, null=True, blank=True, related_name='devices')

    is_active = models.BooleanField(default=True, help_text="Uncheck to revoke a device's API key access.")
    registered_at = models.DateTimeField(auto_now_add=True)
    last_seen = models.DateTimeField(null=True, blank=True)
    last_sync = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-last_seen']

    def __str__(self):
        return f"{self.hostname} ({self.employee or 'unassigned'})"

    @property
    def is_online(self):
        if not self.last_seen:
            return False
        cutoff = timezone.now() - timedelta(minutes=settings.DEVICE_OFFLINE_AFTER_MINUTES)
        return self.last_seen >= cutoff

    def touch(self):
        self.last_seen = timezone.now()
        self.save(update_fields=['last_seen'])


class Asset(models.Model):
    """Current hardware snapshot for a device. Overwritten on every sync;
    AssetChangeLog is what preserves history."""

    device = models.OneToOneField(Device, on_delete=models.CASCADE, related_name='asset')

    cpu_name = models.CharField("System Model (Cabinet)", max_length=200, blank=True)
    cpu_serial = models.CharField(max_length=120, blank=True)
    processor = models.CharField(max_length=200, blank=True)

    motherboard_manufacturer = models.CharField(max_length=150, blank=True)
    motherboard_model = models.CharField(max_length=150, blank=True)
    motherboard_serial = models.CharField(max_length=120, blank=True)
    bios_serial = models.CharField(max_length=120, blank=True)

    ram_total = models.CharField(max_length=40, blank=True)
    ram_devices = models.JSONField(default=list, blank=True)   # list of {slot, size, serial, ...}

    storage_devices = models.JSONField(default=list, blank=True)  # list of {name, serial, size, type, ...}

    monitor_name = models.CharField(max_length=150, blank=True)
    monitor_serial = models.CharField(max_length=120, blank=True)
    monitor_manufacturer = models.CharField(max_length=150, blank=True)

    mouse_name = models.CharField(max_length=150, blank=True)
    mouse_serial = models.CharField(max_length=120, blank=True)
    keyboard_name = models.CharField(max_length=150, blank=True)
    keyboard_serial = models.CharField(max_length=120, blank=True)

    ups_name = models.CharField(max_length=150, blank=True)
    ups_serial = models.CharField(max_length=120, blank=True)
    ups_capacity = models.CharField(max_length=60, blank=True)

    asset_tag = models.CharField(max_length=80, blank=True)
    vendor = models.CharField(max_length=150, blank=True)
    purchase_date = models.CharField(max_length=60, blank=True)
    handover_date = models.CharField(max_length=60, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Asset snapshot for {self.device.hostname}"

    # Fields compared field-by-field on every sync to build the audit
    # trail. JSON list fields (ram_devices, storage_devices) are handled
    # separately in change_detection.py.
    SCALAR_TRACKED_FIELDS = [
        'cpu_name', 'cpu_serial', 'processor',
        'motherboard_manufacturer', 'motherboard_model', 'motherboard_serial', 'bios_serial',
        'ram_total',
        'monitor_name', 'monitor_serial', 'monitor_manufacturer',
        'mouse_name', 'mouse_serial', 'keyboard_name', 'keyboard_serial',
        'ups_name', 'ups_serial', 'ups_capacity',
    ]


class AssetChangeLog(models.Model):
    """Permanent audit trail -- append-only, never edited or deleted by
    the sync process (§5: previous details, new details, timestamp,
    employee, branch, computer name, serials, type of modification)."""

    CHANGE_TYPES = [
        ('Added', 'Added'),
        ('Removed', 'Removed'),
        ('Replaced', 'Replaced'),
        ('Updated', 'Updated'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='change_logs')
    field_name = models.CharField(max_length=60)
    change_type = models.CharField(max_length=10, choices=CHANGE_TYPES)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)

    # Denormalized snapshot of context at the time of change, so the
    # history entry stays meaningful even if the employee/branch later
    # changes on the Device record itself.
    employee_name = models.CharField(max_length=120, blank=True)
    branch_name = models.CharField(max_length=120, blank=True)
    computer_name = models.CharField(max_length=120, blank=True)

    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-changed_at']
        verbose_name = "Asset Change (Audit Log)"
        verbose_name_plural = "Asset Changes (Audit Log)"

    def __str__(self):
        return f"{self.device.hostname}: {self.field_name} {self.change_type} @ {self.changed_at:%Y-%m-%d %H:%M}"


class Printer(models.Model):
    """Shared per-branch asset -- matches the company's existing Printers
    sheet columns exactly."""
    brand = models.CharField(max_length=150)
    model = models.CharField(max_length=150, blank=True)
    serial_number = models.CharField(max_length=120, blank=True)
    date_purchased = models.CharField(max_length=60, blank=True)
    warranty_expiry = models.CharField(max_length=60, blank=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True, related_name='printers')
    location = models.CharField(max_length=150, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['brand']

    def __str__(self):
        return f"{self.brand} {self.model}".strip()


class SyncLog(models.Model):
    """One row per sync attempt -- powers 'last sync' displays and
    'synchronization failed' notifications."""
    STATUS_CHOICES = [('success', 'Success'), ('failed', 'Failed')]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='sync_logs')
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    detail = models.TextField(blank=True)
    synced_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-synced_at']

    def __str__(self):
        return f"{self.device.hostname} sync {self.status} @ {self.synced_at:%Y-%m-%d %H:%M}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('new_device', 'New computer registered'),
        ('new_employee', 'New employee added'),
        ('hardware_change', 'Hardware replacement detected'),
        ('device_offline', 'Device removed from the network'),
        ('sync_failed', 'Synchronization failed'),
        ('duplicate_asset', 'Duplicate asset detected'),
        ('missing_info', 'Missing hardware information'),
    ]
    SEVERITY_CHOICES = [('info', 'Info'), ('warning', 'Warning'), ('critical', 'Critical')]

    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='info')
    message = models.CharField(max_length=500)
    device = models.ForeignKey(Device, on_delete=models.CASCADE, null=True, blank=True, related_name='notifications')
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, null=True, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.severity}] {self.message[:60]}"


class Command(models.Model):
    """Two-way communication (§10): the admin queues an instruction here;
    the device picks it up on its next sync/heartbeat call and reports
    back completion."""

    COMMAND_TYPES = [
        ('force_scan', 'Request immediate hardware scan'),
        ('force_sync', 'Force synchronization'),
        ('update_employee', 'Update employee information'),
        ('correct_asset', 'Correct asset details'),
        ('change_settings', 'Change application settings'),
        ('announcement', 'Send announcement/instruction'),
        ('maintenance_reminder', 'Schedule maintenance reminder'),
    ]
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('delivered', 'Delivered'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
    ]

    device = models.ForeignKey(Device, on_delete=models.CASCADE, related_name='commands')
    command_type = models.CharField(max_length=20, choices=COMMAND_TYPES)
    payload = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='pending')

    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    result_detail = models.TextField(blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.command_type} -> {self.device.hostname} ({self.status})"
