from django.contrib import admin
from django.urls import path, include

from core import public_views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
    path('download/', public_views.download_page, name='download-page'),
]

admin.site.site_header = "Enterprise Asset Management"
admin.site.site_title = "Asset Management Admin"
admin.site.index_title = "Central Asset Dashboard"
