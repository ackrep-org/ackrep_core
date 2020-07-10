import os
import pprint
from django.views import View
from django.shortcuts import render
from django.http import Http404
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


class EntityDetailView(View):
    # noinspection PyMethodMayBeStatic
    def get(self, request, key):

        try:
            entity = core.get_entity(key)
        except ValueError as ve:
            raise Http404(ve)

        context = {"entity": entity,
                   }

        # create an object container (entity.oc) where for each string-keys the real object is available
        core.resolve_keys(entity)

        return render(request, "ackrep_web/entity_detail.html", context)


class CheckSolutionView(View):
    # noinspection PyMethodMayBeStatic
    def get(self, request, key):

        try:
            entity = core.get_entity(key)
        except ValueError as ve:
            raise Http404(ve)

        # TODO: spawn a new container and shown some status updates while the user is waiting

        cs_result = core.check_solution(key)

        context = {"entity": entity,
                   "check-solution": True,
                   "cs_result": cs_result,
                   }

        # create an object container (entity.oc) where for each string-keys the real object is available
        core.resolve_keys(entity)

        return render(request, "ackrep_web/entity_detail.html", context)


class ImportRepoView(View):

    # noinspection PyMethodMayBeStatic
    def get(self, request):

        context = {}

        # clone git repo
        # import into database
        #

        return render(request, "ackrep_web/landing.html", context)
