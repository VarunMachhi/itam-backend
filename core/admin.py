from datetime import datetime

from django import forms
from django.contrib import admin
from django.utils.html import format_html, format_html_join

from core import excel_export
from core.models import AppRelease, Asset, AssetChangeLog, Branch, Command, Device, Employee, Notification, Printer, SyncLog
from core.versioning import is_newer


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'device_count', 'employee_count', 'created_at']
    search_fields = ['name', 'address']

    def device_count(self, obj):
        return obj.devices.count()

    def employee_count(self, obj):
        return obj.employees.count()


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ['name', 'designation', 'department', 'branch']
    list_filter = ['branch', 'department']
    search_fields = ['name', 'designation', 'department']


class AssetInline(admin.StackedInline):
    model = Asset
    can_delete = False
    extra = 0
    readonly_fields = [f.name for f in Asset._meta.fields if f.name not in
                        ('id', 'device', 'ram_devices', 'storage_devices', 'serial_verification')] + \
                       ['ram_devices_display', 'storage_devices_display', 'serial_verification_display']
    fields = [f.name for f in Asset._meta.fields if f.name not in
              ('id', 'device', 'ram_devices', 'storage_devices', 'serial_verification')] + \
             ['ram_devices_display', 'storage_devices_display', 'serial_verification_display']

    def ram_devices_display(self, obj):
        devices = obj.ram_devices or []
        if not devices:
            return "No RAM device details recorded."
        return format_html('<ul style="margin:0; padding-left:18px;">{}</ul>', format_html_join(
            '', '<li><b>Slot {}:</b> {} {} {} @ {} (SN: {})</li>',
            ((d.get('slot', '?'), d.get('size', '?'), d.get('manufacturer', ''),
              d.get('part_number', ''), d.get('speed', '?'), d.get('serial', 'unknown'))
             for d in devices)
        ))
    ram_devices_display.short_description = "RAM Devices"

    def storage_devices_display(self, obj):
        devices = obj.storage_devices or []
        if not devices:
            return "No storage device details recorded."
        return format_html('<ul style="margin:0; padding-left:18px;">{}</ul>', format_html_join(
            '', '<li><b>{}</b> \u2014 {} {} ({}), SN: {}</li>',
            ((d.get('name') or d.get('model', 'Unknown drive'), d.get('size', '?'),
              d.get('type', ''), d.get('interface', '?'), d.get('serial', 'unknown'))
             for d in devices)
        ))
    storage_devices_display.short_description = "Storage Devices"

    def serial_verification_display(self, obj):
        entries = obj.serial_verification or {}
        if not entries:
            return "No manual serial corrections recorded."
        rows = []
        for field_name, info in entries.items():
            label = field_name.replace('_', ' ').title()
            detected = info.get('detected')
            current = info.get('current', '?')
            verified_by = info.get('verified_by', 'unknown')
            verified_at_raw = info.get('verified_at', '')
            try:
                verified_at = datetime.fromisoformat(verified_at_raw).strftime('%b %d, %Y %I:%M %p')
            except (ValueError, TypeError):
                verified_at = verified_at_raw or 'unknown time'
            detected_note = f"auto-detect found \u201c{detected}\u201d, corrected" if detected else \
                "auto-detect found nothing"
            rows.append((label, current, detected_note, verified_by, verified_at))
        return format_html('<ul style="margin:0; padding-left:18px;">{}</ul>', format_html_join(
            '', '<li><b>{}:</b> {} \u2014 {}; verified by {} on {}</li>', rows
        ))
    serial_verification_display.short_description = "Manually Verified Serials"


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['hostname', 'employee', 'branch', 'device_type', 'status_badge',
                     'app_version', 'version_status', 'last_seen', 'last_sync', 'is_active']
    list_filter = ['branch', 'device_type', 'is_active']
    search_fields = ['hostname', 'mac_address', 'employee__name', 'id']
    readonly_fields = ['id', 'api_key', 'registered_at', 'last_seen', 'last_sync']
    inlines = [AssetInline]
    actions = ['deactivate_devices', 'reactivate_devices', 'export_to_excel']

    def status_badge(self, obj):
        color = '#2e7d32' if obj.is_online else '#c62828'
        label = 'Online' if obj.is_online else 'Offline'
        return format_html('<b style="color:{}">{}</b>', color, label)
    status_badge.short_description = 'Status'

    def version_status(self, obj):
        """Flags devices running behind the current latest stable release,
        so an admin can see update rollout progress across branches at a
        glance (\u00a713 'track update success/failure across branches')
        without having to open each device individually."""
        if not obj.app_version:
            return format_html('<span style="{}">Unknown</span>', 'color:#999')
        latest = AppRelease.objects.filter(channel='stable', is_latest=True, is_active=True).first()
        if latest is None:
            return ''
        if is_newer(latest.version, obj.app_version):
            return format_html('<span style="color:#c62828">\u26a0 Behind (latest: {})</span>', latest.version)
        return format_html('<span style="{}">{} Current</span>', 'color:#2e7d32', '\u2713')
    version_status.short_description = 'Update Status'

    @admin.action(description="Deactivate selected devices (revokes API key access)")
    def deactivate_devices(self, request, queryset):
        queryset.update(is_active=False)

    @admin.action(description="Reactivate selected devices")
    def reactivate_devices(self, request, queryset):
        queryset.update(is_active=True)

    @admin.action(description="\U0001F4CA Export selected to Excel")
    def export_to_excel(self, request, queryset):
        queryset = queryset.select_related('employee', 'branch', 'asset')
        wb = excel_export.build_devices_workbook(queryset)
        return excel_export.workbook_response(wb, "Asset_Inventory.xlsx")


@admin.register(AssetChangeLog)
class AssetChangeLogAdmin(admin.ModelAdmin):
    list_display = ['changed_at', 'computer_name', 'employee_name', 'branch_name',
                     'field_name', 'change_type', 'old_value_short', 'new_value_short']
    list_filter = ['change_type', 'field_name', 'branch_name']
    search_fields = ['computer_name', 'employee_name', 'old_value', 'new_value']
    date_hierarchy = 'changed_at'
    actions = ['export_to_excel']

    def has_add_permission(self, request):
        return False  # audit log is system-generated only

    def has_change_permission(self, request, obj=None):
        return False  # append-only

    def old_value_short(self, obj):
        return (obj.old_value[:40] + '…') if len(obj.old_value) > 40 else obj.old_value

    def new_value_short(self, obj):
        return (obj.new_value[:40] + '…') if len(obj.new_value) > 40 else obj.new_value

    @admin.action(description="\U0001F4CA Export selected to Excel")
    def export_to_excel(self, request, queryset):
        wb = excel_export.build_change_log_workbook(queryset)
        return excel_export.workbook_response(wb, "Asset_Change_History.xlsx")


@admin.register(Printer)
class PrinterAdmin(admin.ModelAdmin):
    list_display = ['brand', 'model', 'serial_number', 'branch', 'location',
                     'date_purchased', 'warranty_expiry']
    list_filter = ['branch']
    search_fields = ['brand', 'model', 'serial_number', 'location']
    actions = ['export_to_excel']

    @admin.action(description="\U0001F4CA Export selected to Excel")
    def export_to_excel(self, request, queryset):
        wb = excel_export.build_printers_workbook(queryset.select_related('branch'))
        return excel_export.workbook_response(wb, "Printers_Inventory.xlsx")


@admin.register(SyncLog)
class SyncLogAdmin(admin.ModelAdmin):
    list_display = ['synced_at', 'device', 'status', 'detail']
    list_filter = ['status']
    search_fields = ['device__hostname', 'detail']
    date_hierarchy = 'synced_at'

    def has_add_permission(self, request):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'type', 'severity', 'message_short', 'device', 'branch', 'is_read']
    list_filter = ['type', 'severity', 'is_read']
    search_fields = ['message']
    actions = ['mark_read', 'mark_unread']

    def message_short(self, obj):
        return (obj.message[:80] + '…') if len(obj.message) > 80 else obj.message

    @admin.action(description="Mark selected as read")
    def mark_read(self, request, queryset):
        queryset.update(is_read=True)

    @admin.action(description="Mark selected as unread")
    def mark_unread(self, request, queryset):
        queryset.update(is_read=False)


class CommandForm(forms.ModelForm):
    """Replaces the raw JSON 'payload' field with a plain text box -- an
    admin creating a command shouldn't need to know JSON syntax just to
    type an instruction. Currently the only payload shape used anywhere
    (client and admin) is {'message': '...'}, so this form is the single
    place that JSON structure lives; if a second payload field is ever
    needed, extend both this form and the client's payload.get(...) calls
    together."""
    message = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 3}), required=False,
        help_text="The instruction/message shown to the employee -- plain text, no JSON needed.")

    class Meta:
        model = Command
        exclude = ['payload']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and isinstance(self.instance.payload, dict):
            self.fields['message'].initial = self.instance.payload.get('message', '')

    def save(self, commit=True):
        instance = super().save(commit=False)
        instance.payload = {'message': self.cleaned_data.get('message', '')}
        if commit:
            instance.save()
        return instance


@admin.register(Command)
class CommandAdmin(admin.ModelAdmin):
    form = CommandForm
    list_display = ['created_at', 'device', 'command_type', 'status', 'delivered_at', 'completed_at']
    list_filter = ['command_type', 'status']
    search_fields = ['device__hostname']
    readonly_fields = ['delivered_at', 'completed_at', 'result_detail']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class AppReleaseForm(forms.ModelForm):
    """Requires a SHA-256 whenever a release is marked 'is_latest' -- the
    client now hard-refuses to install any update with no published
    checksum (see asset_manager.py's _download_update_file), since a
    missing hash was very likely the reason corrupted downloads were
    installing successfully on more than one machine. This mirrors that
    requirement here, so the mistake gets caught at publish time instead
    of only being discovered later on an employee's PC."""

    class Meta:
        model = AppRelease
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('is_latest') and not cleaned_data.get('sha256'):
            raise forms.ValidationError(
                "A SHA-256 checksum is required before a release can be marked 'Is latest' -- "
                "copy it from the GitHub Release page's Assets list (use the copy icon, not the "
                "truncated display text) and paste the full 64-character value here.")
        return cleaned_data


@admin.register(AppRelease)
class AppReleaseAdmin(admin.ModelAdmin):
    form = AppReleaseForm
    list_display = ['version', 'channel', 'latest_badge', 'is_mandatory', 'is_active', 'published_at']
    list_filter = ['channel', 'is_active', 'is_mandatory']
    search_fields = ['version', 'changelog']
    readonly_fields = ['published_at']
    actions = ['mark_as_latest', 'pull_release']

    def latest_badge(self, obj):
        if not obj.is_latest:
            return ''
        return format_html('<b style="{}">{} Latest</b>', 'color:#2e7d32', '\u2605')
    latest_badge.short_description = 'Status'

    @admin.action(description="\u2605 Mark as latest (for its channel)")
    def mark_as_latest(self, request, queryset):
        if queryset.count() != 1:
            self.message_user(request, "Select exactly one release to mark as latest.", level='error')
            return
        release = queryset.first()
        if not release.sha256:
            self.message_user(
                request,
                f"Can't mark {release} as latest -- it has no SHA-256 checksum. "
                f"Open it and add one first (copy via the icon on the GitHub Release "
                f"page, not the truncated display text).", level='error')
            return
        release.is_latest = True
        release.is_active = True
        release.save()
        self.message_user(request, f"{release} is now the latest {release.get_channel_display()} release.")

    @admin.action(description="Pull selected release(s) from circulation")
    def pull_release(self, request, queryset):
        queryset.update(is_active=False, is_latest=False)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
