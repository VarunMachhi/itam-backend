from django.conf import settings
from django.db import transaction
from django.utils import timezone
from rest_framework import permissions, status
from rest_framework.response import Response
from rest_framework.views import APIView

from core import change_detection
from core.authentication import DeviceKeyAuthentication
from core.models import Asset, AssetChangeLog, Branch, Command, Device, Employee, Notification, SyncLog
from core.serializers import (
    CommandResultSerializer, CommandSerializer, DeviceRegistrationSerializer, SyncRequestSerializer,
)


class IsDevice(permissions.BasePermission):
    """Only requests authenticated via DeviceKeyAuthentication may proceed."""
    def has_permission(self, request, view):
        return bool(request.user and getattr(request.user, 'is_authenticated', False)
                    and hasattr(request.user, 'device'))


class DeviceRegisterView(APIView):
    """POST /api/devices/register/
    No device auth required (a device doesn't have a key yet) -- gated
    instead by the shared DEVICE_ENROLLMENT_KEY, which is what stops
    arbitrary devices from self-registering (§11)."""
    authentication_classes = []
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = DeviceRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        if data['enrollment_key'] != settings.DEVICE_ENROLLMENT_KEY:
            return Response({'detail': 'Invalid enrollment key.'}, status=status.HTTP_403_FORBIDDEN)

        branch = None
        if data.get('branch_name'):
            branch, _ = Branch.objects.get_or_create(name=data['branch_name'].strip())

        employee = None
        if data.get('employee_name'):
            employee, _ = Employee.objects.get_or_create(
                name=data['employee_name'].strip(),
                branch=branch,
                defaults={'designation': data.get('designation', ''), 'department': data.get('department', '')},
            )

        # Re-registration safety: if this exact hostname+mac already exists
        # (e.g. the app was reinstalled), reuse the existing device/history
        # instead of creating a duplicate row (§6 "duplicate asset detected").
        existing = None
        if data.get('mac_address'):
            existing = Device.objects.filter(mac_address=data['mac_address'], hostname=data['hostname']).first()

        is_new = existing is None
        device = existing or Device()
        device.hostname = data['hostname']
        device.mac_address = data.get('mac_address', '')
        device.ip_address = data.get('ip_address', '')
        device.os_info = data.get('os_info', '')
        device.device_type = data.get('device_type', 'Unknown')
        device.branch = branch or device.branch
        device.employee = employee or device.employee
        device.is_active = True
        device.last_seen = timezone.now()
        device.save()

        if is_new:
            Notification.objects.create(
                type='new_device', severity='info', device=device, branch=branch,
                message=f"New computer registered: {device.hostname} ({device.device_type})"
                        f"{' - ' + employee.name if employee else ''}",
            )
        else:
            Notification.objects.create(
                type='duplicate_asset', severity='info', device=device, branch=branch,
                message=f"Existing device re-registered (reused history): {device.hostname}",
            )

        return Response({
            'device_id': str(device.id),
            'api_key': device.api_key,
            'is_new': is_new,
        }, status=status.HTTP_201_CREATED if is_new else status.HTTP_200_OK)


class SyncView(APIView):
    """POST /api/sync/
    The main two-way endpoint (§3, §7): device uploads its current
    hardware scan, server runs change detection (§4) and writes audit
    history (§5), and returns any pending admin commands (§10)."""
    authentication_classes = [DeviceKeyAuthentication]
    permission_classes = [IsDevice]

    def post(self, request):
        device = request.user.device
        serializer = SyncRequestSerializer(data=request.data)
        if not serializer.is_valid():
            SyncLog.objects.create(device=device, status='failed', detail=str(serializer.errors))
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        data = serializer.validated_data
        asset_data = data['asset']

        try:
            with transaction.atomic():
                if data.get('employee_name'):
                    employee, _ = Employee.objects.get_or_create(
                        name=data['employee_name'].strip(), branch=device.branch,
                        defaults={'designation': data.get('designation', ''),
                                  'department': data.get('department', '')},
                    )
                    device.employee = employee

                if data.get('ip_address'):
                    device.ip_address = data['ip_address']
                device.last_seen = timezone.now()
                device.last_sync = timezone.now()
                device.save()

                existing_asset = Asset.objects.filter(device=device).first()
                is_first_sync = existing_asset is None

                changes = [] if is_first_sync else change_detection.diff_asset(existing_asset, asset_data)

                if existing_asset is None:
                    existing_asset = Asset(device=device)
                for field, value in asset_data.items():
                    setattr(existing_asset, field, value)
                existing_asset.save()

                for change in changes:
                    AssetChangeLog.objects.create(
                        device=device,
                        field_name=change['field_name'],
                        change_type=change['change_type'],
                        old_value=change['old_value'],
                        new_value=change['new_value'],
                        employee_name=device.employee.name if device.employee else '',
                        branch_name=device.branch.name if device.branch else '',
                        computer_name=device.hostname,
                    )

                if changes:
                    summary = '; '.join(f"{c['field_name']} {c['change_type']}" for c in changes[:5])
                    Notification.objects.create(
                        type='hardware_change', severity='warning', device=device, branch=device.branch,
                        message=f"Hardware change detected on {device.hostname}: {summary}"
                                f"{' (+more)' if len(changes) > 5 else ''}",
                    )

                SyncLog.objects.create(device=device, status='success',
                                        detail=f"{len(changes)} change(s) recorded" if changes else "No changes")
        except Exception as exc:  # noqa: BLE001 -- deliberately broad: any failure must still be logged
            SyncLog.objects.create(device=device, status='failed', detail=str(exc))
            raise

        pending_commands = Command.objects.filter(device=device, status='pending')
        pending_commands.update(status='delivered', delivered_at=timezone.now())

        return Response({
            'synced_at': device.last_sync,
            'changes_detected': len(changes),
            'commands': CommandSerializer(pending_commands, many=True).data,
        })


class HeartbeatView(APIView):
    """POST /api/heartbeat/
    Lightweight check-in between full syncs, just to keep Online/Offline
    status accurate without re-uploading the whole hardware scan."""
    authentication_classes = [DeviceKeyAuthentication]
    permission_classes = [IsDevice]

    def post(self, request):
        device = request.user.device
        device.touch()
        pending_exists = Command.objects.filter(device=device, status='pending').exists()
        return Response({'ok': True, 'commands_pending': pending_exists})


class PendingCommandsView(APIView):
    """GET /api/commands/pending/ -- devices can poll this directly
    instead of waiting for their next full sync."""
    authentication_classes = [DeviceKeyAuthentication]
    permission_classes = [IsDevice]

    def get(self, request):
        device = request.user.device
        commands = Command.objects.filter(device=device, status='pending')
        commands.update(status='delivered', delivered_at=timezone.now())
        return Response(CommandSerializer(commands, many=True).data)


class CommandResultView(APIView):
    """POST /api/commands/<id>/result/ -- device reports back whether an
    instruction succeeded, closing the loop on §10 two-way communication."""
    authentication_classes = [DeviceKeyAuthentication]
    permission_classes = [IsDevice]

    def post(self, request, command_id):
        device = request.user.device
        try:
            command = Command.objects.get(id=command_id, device=device)
        except Command.DoesNotExist:
            return Response({'detail': 'Command not found for this device.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = CommandResultSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        command.status = serializer.validated_data['status']
        command.result_detail = serializer.validated_data.get('result_detail', '')
        command.completed_at = timezone.now()
        command.save()
        return Response(CommandSerializer(command).data)
