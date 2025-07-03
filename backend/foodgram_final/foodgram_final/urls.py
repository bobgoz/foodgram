from django.contrib import admin
from django.urls import path, include, re_path

from api.urls import router
from api.views import ShortLinkRedirectView


urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    path('api/', include('djoser.urls')),
    path('api/auth/', include('djoser.urls.authtoken')),
    re_path(
        r'^api/s/(?P<short_url>[a-zA-Z0-9]{6})/$',
        ShortLinkRedirectView.as_view(),
        name='short-link-redirect'),
]
