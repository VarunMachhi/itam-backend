from django.urls import path

from core import views

urlpatterns = [
    path('devices/register/', views.DeviceRegisterView.as_view(), name='device-register'),
    path('sync/', views.SyncView.as_view(), name='sync'),
    path('heartbeat/', views.HeartbeatView.as_view(), name='heartbeat'),
    path('commands/pending/', views.PendingCommandsView.as_view(), name='commands-pending'),
    path('commands/<int:command_id>/result/', views.CommandResultView.as_view(), name='command-result'),
    path('app/latest/', views.AppLatestVersionView.as_view(), name='app-latest-version'),
]
