import time
import pprint
from django.views import View
from django.shortcuts import render
from django.http import Http404
from django.utils import timezone
from ackrep_core import util
from ackrep_core import core

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception


class LandingPageView(View):

    # noinspection PyMethodMayBeStatic
    def get(self, request):

        entity_dict = core.get_entity_dict_from_db()
        nr_of_entities = sum(len(entity_list) for type_name, entity_list in entity_dict.items())
        context = {"nr_of_entities": nr_of_entities}

        return render(request, "ackrep_web/landing.html", context)


class EntityListView(View):
    # noinspection PyMethodMayBeStatic
    def get(self, request):

        #core.load_repo_to_db(core.data_path)

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

        c = core.Container()

        c.entity = entity
        c.view_type = "detail"
        c.view_type_title = "Details for:"

        context = {"c": c}

        # create an object container (entity.oc) where for each string-keys the real object is available
        core.resolve_keys(entity)

        return render(request, "ackrep_web/entity_detail.html", context)


class CheckSolutionView(View):
    # noinspection PyMethodMayBeStatic
    def get(self, request, key):

        try:
            sol_entity = core.get_entity(key)
        except ValueError as ve:
            raise Http404(ve)

        # TODO: spawn a new container and shown some status updates while the user is waiting

        core.resolve_keys(sol_entity)

        c = core.Container()
        ts1 = timezone.now()
        cs_result = core.check_solution(key)
        c.diff_time_str = util.smooth_timedelta(ts1)

        c.entity = sol_entity
        c.view_type = "check-solution"
        c.view_type_title = "Check Solution for:"
        c.cs_result = cs_result

        c.image_list = core.get_solution_data_files(sol_entity.base_path, endswith_str=".png", create_media_links=True)

        if cs_result.returncode == 0:
            c.cs_result_css_class = "cs_success"
            c.cs_verbal_result = "Success"
            # c.debug = cs_result
        else:
            c.cs_result_css_class = "cs_fail"
            c.cs_verbal_result = "Fail"
            c.debug = cs_result

        context = {"c": c}

        # create an object container (entity.oc) where for each string-key the real object is available

        return render(request, "ackrep_web/entity_detail.html", context)


class ImportRepoView(View):

    # noinspection PyMethodMayBeStatic
    def get(self, request):

        context = {}

        # clone git repo
        # import into database
        #

        return render(request, "ackrep_web/landing.html", context)
