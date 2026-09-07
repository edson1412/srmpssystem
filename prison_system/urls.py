# prison_system/urls.py

"""
URL configuration for prison_system project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from prison import views as prison_views

# Error handler views
handler400 = 'prison.views.error_400'
handler403 = 'prison.views.error_403'
handler404 = 'prison.views.error_404'
handler405 = 'prison.views.error_405'
handler500 = 'prison.views.error_500'
handler502 = 'prison.views.error_502'
handler503 = 'prison.views.error_503'
handler504 = 'prison.views.error_504'
handler413 = 'prison.views.error_413'
handler429 = 'prison.views.error_429'

# CSRF failure handler
CSRF_FAILURE_VIEW = 'prison.views.csrf_failure_view'

urlpatterns = [
    # Admin site
    path('admin/', admin.site.urls),

    # Main prison app (dashboard, prisoners, visitors, medical, incidents, etc.)
    path('', include('prison.urls')),

    # Accounts app (login, logout, user management)
    path('accounts/', include('accounts.urls')),

    # Returns app (returns management, templates, submissions, exports)
    path('returns/', include('returns.urls')),
]

# Serve media files in development
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
else:
    # In production, media files should be served by web server
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Serve static files in development (if not handled by whitenoise)
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)