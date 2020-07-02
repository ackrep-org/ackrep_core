from django.conf.urls import url
from django.urls import path
from . import views

urlpatterns = [
  url(r'^$', views.LandingPageView.as_view(), name='landing-page'),
  path('login', views.LandingPageView.as_view(), name='login'),
  ]
