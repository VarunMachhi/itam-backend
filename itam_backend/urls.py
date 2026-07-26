from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include('core.urls')),
]

admin.site.site_header = "Enterprise Asset Management"
admin.site.site_title = "Asset Management Admin"
admin.site.index_title = "Central Asset Dashboard"
