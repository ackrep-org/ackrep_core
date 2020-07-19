import time
import pprint
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.template.response import TemplateResponse
from django.shortcuts import redirect, reverse
from django.http import Http404
from django.utils import timezone
from django.contrib import messages
from ackrep_core import util
from ackrep_core import core
from git.exc import GitCommandError

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception


class LandingPageView(View):

    # noinspection PyMethodMayBeStatic
    def get(self, request):

        entity_dict = core.get_entity_dict_from_db()
        nr_of_entities = sum(len(entity_list) for type_name, entity_list in entity_dict.items())
        context = {"nr_of_entities": nr_of_entities}

        return TemplateResponse(request, "ackrep_web/landing.html", context)


class EntityListView(View):
    # noinspection PyMethodMayBeStatic
    def get(self, request):

        #core.load_repo_to_db(core.data_path)

        entity_dict = core.get_entity_dict_from_db()

        context = {"title": "Entity List",
                   "entity_list": pprint.pformat(entity_dict),
                   "entity_dict": entity_dict
                   }

        return TemplateResponse(request, "ackrep_web/entity_list.html", context)


class ImportCanonicalView(View):
    # noinspection PyMethodMayBeStatic
    def post(self, request):
        entity_list = core.load_repo_to_db(core.data_path)

        return redirect("imported-entities")


class ImportedEntitiesView(View):
    # noinspection PyMethodMayBeStatic
    def get(self, request):
        entity_list = core.last_loaded_entities

        context = {"entity_list": entity_list}

        return TemplateResponse(request, "ackrep_web/imported_entities.html", context)


class ClearDatabaseView(View):
    # noinspection PyMethodMayBeStatic
    def post(self, request):
        core.clear_db()

        print("Cleared DB")

        return redirect("landing-page")


class ExtendDatabaseView(View):
    def get(self, request):
        context = {}

        return TemplateResponse(request, "ackrep_web/extend_database.html", context)

    def post(self, request):
        url = request.POST.get("external_repo_url", "")

        try:
            core.last_loaded_entities = []  # HACK!
            local_dir = core.clone_external_data_repo(url)
            core.extend_db(local_dir)
            messages.success(request, f"Repository at '{url}' imported")
        except GitCommandError as e:
            git_error = e.args[2].decode("utf-8")
            messages.error(request, f"An error occurred: {git_error}")

        return redirect("imported-entities")


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

        return TemplateResponse(request, "ackrep_web/entity_detail.html", context)


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

        return TemplateResponse(request, "ackrep_web/entity_detail.html", context)


class ImportRepoView(View):

    # noinspection PyMethodMayBeStatic
    def get(self, request):

        context = {}

        # clone git repo
        # import into database
        #

        return TemplateResponse(request, "ackrep_web/landing.html", context)
