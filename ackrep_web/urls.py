from django.conf.urls import url
from django.urls import path
from . import views

urlpatterns = [
  url(r'^$', views.LandingPageView.as_view(), name='landing-page'),
  path('login', views.LandingPageView.as_view(), name='login'),

  # placeholders
  path('imprint', views.LandingPageView.as_view(), name='imprint-page'),
  path('privacy', views.LandingPageView.as_view(), name='privacy-page'),
  path('contact', views.LandingPageView.as_view(), name='contact-page'),
  ]

