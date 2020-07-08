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

        data_path = os.path.join(core.mod_path, "..", "..", "ackrep_data")
        core.load_repo_to_db(data_path)
        entity_type_list = core.models.get_entities()

        result = {}

        for et in entity_type_list:

            object_list = list(et.objects.all())

            result[et.__name__] = object_list

        context = {"title": "Entity List",
                   "entity_list": pprint.pformat(result)
                   }

        return render(request, "ackrep_web/generic_content.html", context)


class ImportRepoView(View):

    # noinspection PyMethodMayBeStatic
    def get(self, request):

        context = {}

        # clone git repo
        # import into database
        #

        return render(request, "ackrep_web/landing.html", context)
