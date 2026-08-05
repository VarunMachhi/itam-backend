from django.contrib import admin
from django.utils.html import format_html

from core import excel_export
from core.models import AppRelease, Asset, AssetChangeLog, Branch, Command, Device, Employee, Notification, Printer, SyncLog


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
    readonly_fields = [f.name for f in Asset._meta.fields if f.name not in ('id', 'device')]
    extra = 0


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ['hostname', 'employee', 'branch', 'device_type', 'status_badge',
                     'last_seen', 'last_sync', 'is_active']
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


@admin.register(Command)
class CommandAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'device', 'command_type', 'status', 'delivered_at', 'completed_at']
    list_filter = ['command_type', 'status']
    search_fields = ['device__hostname']
    readonly_fields = ['delivered_at', 'completed_at', 'result_detail']

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(AppRelease)
class AppReleaseAdmin(admin.ModelAdmin):
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
