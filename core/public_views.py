"""
Plain (non-API) views meant for a human browser, not the device client --
kept separate from views.py (which is exclusively DRF/JSON) so the two
concerns don't get tangled together.
"""
from django.shortcuts import render

from core.models import AppRelease


def download_page(request):
    """GET /download/ -- public web page (§1 of the deployment plan): an
    employee visits this URL and clicks one button to get the current
    build. Deliberately reads straight from the DB rather than calling
    our own /api/app/latest/ endpoint over HTTP -- no reason to pay the
    extra network round trip when we're already inside the same process."""
    channel = request.GET.get('channel', 'stable')
    release = AppRelease.objects.filter(channel=channel, is_latest=True, is_active=True).first()
    return render(request, 'core/download.html', {'release': release, 'channel': channel})
