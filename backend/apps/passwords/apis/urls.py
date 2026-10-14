from django.urls import include, path

app_name = 'apis'

urlpatterns = [
    path('passwords/', include('apps.passwords.apis.passwords.urls')),
    # Sites and site passwords: logins that aren't at a carrier.
    path('sites/', include('apps.passwords.apis.sites.urls')),
    path('site-passwords/', include('apps.passwords.apis.site_passwords.urls')),
]
