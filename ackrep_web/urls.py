from django.conf.urls import url
from django.urls import path, re_path
from . import views

urlpatterns = [
  url(r'^$', views.LandingPageView.as_view(), name='landing-page'),
  path('entities', views.EntityListView.as_view(), name='entity-list'),
  path('login', views.LandingPageView.as_view(), name='login'),
  re_path('e/(?P<key>[A-Z0-9_]{5})', views.EntityDetailView.as_view(), name='entity-detail'),

  # placeholders
  path('imprint', views.LandingPageView.as_view(), name='imprint-page'),
  path('privacy', views.LandingPageView.as_view(), name='privacy-page'),
  path('contact', views.LandingPageView.as_view(), name='contact-page'),
  ]

