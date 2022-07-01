from django.conf.urls import url
from django.urls import path, re_path
from . import views

urlpatterns = [
    url(r"^$", views.LandingPageView.as_view(), name="landing-page"),
    path("entities", views.EntityListView.as_view(), name="entity-list"),
    path("not-yet-implemented", views.NotYetImplementedView.as_view(), name="not-yet-implemented"),
    path("clear-database", views.ClearDatabaseView.as_view(), name="clear-database"),
    path("import-canonical", views.ImportCanonicalView.as_view(), name="import-canonical"),
    path("update-db", views.UpdateDatabaseView.as_view(), name="update-database"),
    path("imported", views.ImportedEntitiesView.as_view(), name="imported-entities"),
    path("new-mr", views.NewMergeRequestView.as_view(), name="new-merge-request"),
    path("merge-requests", views.MergeRequestListView.as_view(), name="merge-request-list"),
    path("login", views.LandingPageView.as_view(), name="login"),
    path("update-mr", views.UpdateMergeRequestView.as_view(), name="update-merge-request"),
    path("delete-mr", views.DeleteMergeRequestView.as_view(), name="delete-merge-request"),
    path("search-sparql", views.SearchSparqlView.as_view(), name="search-sparql"),
    re_path("mr/(?P<key>[A-Z0-9_]{5})", views.MergeRequestDetailView.as_view(), name="merge-request"),
    re_path("e/(?P<key>[A-Z0-9_]{5})", views.EntityDetailView.as_view(), name="entity-detail"),
    # placeholders
    path("imprint", views.LandingPageView.as_view(), name="imprint-page"),
    path("privacy", views.LandingPageView.as_view(), name="privacy-page"),
    path("contact", views.LandingPageView.as_view(), name="contact-page"),
    path("debug", views.DebugView.as_view(), name="contact-page"),
    path("webhook", views.Webhook.as_view(), name="webhook"),
]
