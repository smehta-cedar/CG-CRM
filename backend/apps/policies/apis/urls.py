from django.urls import include, path

app_name = 'apis'

urlpatterns = [
    path('policy-types/', include('apps.policies.apis.policy_types.urls')),
    path('carrier-policies/', include('apps.policies.apis.carrier_policies.urls')),
    path('certifications/', include('apps.policies.apis.certifications.urls')),
]
