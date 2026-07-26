"""
Devices authenticate with a per-device API key (issued at registration),
NOT a human username/password -- that's what makes "unique device
registration" and "protection against unauthorized devices" (§11)
possible: a revoked/inactive device's key simply stops working.

Header format:  Authorization: Api-Key <the-device-api-key>
"""
from django.utils import timezone
from rest_framework import authentication, exceptions

from core.models import Device


class AuthenticatedDevice:
    """Thin stand-in for a 'user' so DRF's IsAuthenticated permission
    class works unmodified. request.user will be one of these; the
    actual Device row is available as request.user.device."""

    def __init__(self, device: Device):
        self.device = device
        self.is_authenticated = True
        self.is_anonymous = False

    def __str__(self):
        return f"device:{self.device_id}"

    @property
    def pk(self):
        """DRF's built-in rate-limiting (UserRateThrottle) reads
        request.user.pk directly to build its per-user cache key -- this
        object isn't a real Django User, so without this it crashes with
        AttributeError on every single authenticated request (sync,
        heartbeat, commands)."""
        return self.device.id

    @property
    def device_id(self):
        return str(self.device.id)


class DeviceKeyAuthentication(authentication.BaseAuthentication):
    keyword = 'Api-Key'

    def authenticate(self, request):
        auth_header = authentication.get_authorization_header(request).decode('utf-8')
        if not auth_header or not auth_header.startswith(self.keyword):
            return None  # let other authentication classes (admin session login) try

        try:
            key = auth_header.split(' ', 1)[1].strip()
        except IndexError:
            raise exceptions.AuthenticationFailed('Malformed Authorization header.')

        if not key:
            raise exceptions.AuthenticationFailed('Empty API key.')

        try:
            device = Device.objects.select_related('branch', 'employee').get(api_key=key)
        except Device.DoesNotExist:
            raise exceptions.AuthenticationFailed('Invalid device API key.')

        if not device.is_active:
            raise exceptions.AuthenticationFailed('This device has been deactivated by an administrator.')

        return (AuthenticatedDevice(device), None)
