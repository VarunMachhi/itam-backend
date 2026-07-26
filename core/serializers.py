from rest_framework import serializers

from core.models import Asset, Branch, Command, Device, Employee


class DeviceRegistrationSerializer(serializers.Serializer):
    """Body for POST /api/devices/register/. A device sends its own
    enrollment_key (embedded at install time -- see build_exe.bat /
    DEPLOYMENT.md) plus enough identity info to create itself."""
    enrollment_key = serializers.CharField()
    hostname = serializers.CharField(max_length=120)
    mac_address = serializers.CharField(max_length=32, required=False, allow_blank=True)
    ip_address = serializers.CharField(max_length=64, required=False, allow_blank=True)
    os_info = serializers.CharField(max_length=120, required=False, allow_blank=True)
    device_type = serializers.ChoiceField(choices=['Laptop', 'Desktop', 'Unknown'], default='Unknown')

    branch_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    employee_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    designation = serializers.CharField(max_length=120, required=False, allow_blank=True)
    department = serializers.CharField(max_length=120, required=False, allow_blank=True)


class EmployeeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Employee
        fields = ['id', 'name', 'designation', 'department', 'branch']


class AssetSyncSerializer(serializers.ModelSerializer):
    """What the device uploads on every sync -- mirrors the fields
    already produced by asset_manager.py's hardware scan almost 1:1, so
    the client-side mapping stays simple (see DEPLOYMENT.md Phase 2)."""

    class Meta:
        model = Asset
        exclude = ['id', 'device', 'updated_at']


class CommandSerializer(serializers.ModelSerializer):
    class Meta:
        model = Command
        fields = ['id', 'command_type', 'payload', 'status', 'created_at']
        read_only_fields = fields


class CommandResultSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['completed', 'failed'])
    result_detail = serializers.CharField(required=False, allow_blank=True, default='')


class SyncRequestSerializer(serializers.Serializer):
    """Top-level body for POST /api/sync/."""
    ip_address = serializers.CharField(max_length=64, required=False, allow_blank=True)
    employee_name = serializers.CharField(max_length=120, required=False, allow_blank=True)
    designation = serializers.CharField(max_length=120, required=False, allow_blank=True)
    department = serializers.CharField(max_length=120, required=False, allow_blank=True)
    asset = AssetSyncSerializer()
