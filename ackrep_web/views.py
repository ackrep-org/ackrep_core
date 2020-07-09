import os
import pprint
from django.views import View
from django.shortcuts import render
from ackrep_core import core

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception


class LandingPageView(View):

    # noinspection PyMethodMayBeStatic
    def get(self, request):

        context = {}

        return render(request, "ackrep_web/landing.html", context)


class EntityListView(View):
    # noinspection PyMethodMayBeStatic
    def get(self, request):

        core.load_repo_to_db(core.data_path)

        entity_dict = core.get_entity_dict_from_db()

        context = {"title": "Entity List",
                   "entity_list": pprint.pformat(entity_dict),
                   "entity_dict": entity_dict
                   }

        return render(request, "ackrep_web/entity_list.html", context)


class ImportRepoView(View):

    # noinspection PyMethodMayBeStatic
    def get(self, request):

        context = {}

        # clone git repo
        # import into database
        #

        return render(request, "ackrep_web/landing.html", context)
