from django.views import View
from django.shortcuts import render
from ackrep_core import core


class LandingPageView(View):

    # noinspection PyMethodMayBeStatic
    def get(self, request):

        context = {}

        return render(request, "ackrep_web/landing.html", context)


class ImportRepoView(View):

    # noinspection PyMethodMayBeStatic
    def get(self, request):

        context = {}

        # clone git repo
        # import into database
        #

        return render(request, "ackrep_web/landing.html", context)
