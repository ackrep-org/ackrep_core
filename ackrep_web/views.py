import time
from textwrap import dedent as twdd
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
from ackrep_core import models
from git.exc import GitCommandError
from ackrep_core_django_settings import settings
from git import Repo, InvalidGitRepositoryError
import os
import numpy as np

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

        # core.load_repo_to_db(core.data_path)

        entity_dict = core.get_entity_dict_from_db()

        context = {"title": "Entity List", "entity_list": pprint.pformat(entity_dict), "entity_dict": entity_dict}

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


class UpdateDatabaseView(View):
    # noinspection PyMethodMayBeStatic
    def post(self, request):

        return redirect("not-yet-implemented")


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
        if type(entity) == core.models.SystemModel:
            c.pdf_list = core.get_data_files(entity.base_path, endswith_str=".pdf", create_media_links=True)
        c.source_code_links = _create_source_code_links(entity)
        c.source_code_container = _get_source_code(entity)

        context = {"c": c}

        # create an object container (entity.oc) where for each string-keys the real object is available
        core.resolve_keys(entity)

        return TemplateResponse(request, "ackrep_web/entity_detail.html", context)


class CheckView(EntityDetailView):
    def get(self, request, key):
        # inherit cotext data from EntityDetailView like source code and pdf
        c = super().get(request, key).context_data["c"]

        ts1 = timezone.now()
        c.diff_time_str = util.smooth_timedelta(ts1)

        if type(c.entity) == models.ProblemSolution:
            cs_result = core.check_solution(key)
            c.view_type = "check-solution"
            c.view_type_title = "Check Solution for:"

        elif type(c.entity) == models.SystemModel:
            cs_result = core.check_system_model(key)
            c.view_type = "check-system-model"
            c.view_type_title = "Simulation for:"

        else:
            raise TypeError(f"{c.entity} has to be of type ProblemSolution or SystemModel.")

        c.cs_result = cs_result
        c.image_list = core.get_data_files(c.entity.base_path, endswith_str=".png", create_media_links=True)

        c.show_debug = False

        if cs_result.returncode == 0:
            c.cs_result_css_class = "cs_success"
            c.cs_verbal_result = "Success."
            c.show_output = True
        # no major error but numerical result was unexpected
        elif cs_result.returncode == 2:
            c.cs_result_css_class = "cs_inaccurate"
            c.cs_verbal_result = "Inaccurate. (Different result than expected.)"
            c.show_output = True
        else:
            c.cs_result_css_class = "cs_fail"
            c.cs_verbal_result = "Script Error."
            c.show_debug = settings.DEBUG
            c.show_output = False

        context = {"c": c}
        # create an object container (entity.oc) where for each string-key the real object is available

        return TemplateResponse(request, "ackrep_web/entity_detail.html", context)


class NewMergeRequestView(View):

    # noinspection PyMethodMayBeStatic
    def get(self, request):

        context = {}

        return TemplateResponse(request, "ackrep_web/new_merge_request.html", context)

    def post(self, request):
        title = request.POST.get("title", "")
        repo_url = request.POST.get("repo_url", "")
        description = request.POST.get("description", "")

        try:
            mr = core.create_merge_request(repo_url, title, description)

            return redirect("merge-request", key=mr.key)
        except Exception as e:
            error_str = str(e)
            messages.error(request, f"An error occurred: {error_str}")

            return redirect("new-merge-request")


class MergeRequestDetailView(View):
    def get(self, request, key):
        mr = core.get_merge_request(key)
        context = {"mr": mr}

        return TemplateResponse(request, "ackrep_web/merge_request_detail.html", context)


class UpdateMergeRequestView(View):
    def post(self, request):
        return redirect("not-yet-implemented")


class DeleteMergeRequestView(View):
    def post(self, request):
        mr_key = request.POST.get("mr_key", "")

        core.delete_merge_request(core.get_merge_request(mr_key))

        return redirect("merge-request-list")


class MergeRequestListView(View):
    def get(self, request):
        mr_dict = core.get_merge_request_dict()

        context = {"mr_dict": mr_dict}

        return TemplateResponse(request, "ackrep_web/merge_request_list.html", context)


class SearchSparqlView(View):
    def get(self, request):
        context = {}

        # PREFIX P: <{OM.iri}>
        example_query = twdd(
            f"""
        # example query: select all possible tags

        PREFIX P: <https://ackrep.org/draft/ocse-prototype01#>
        SELECT ?entity
        WHERE {{
          ?entity rdf:type ?type.
          ?type rdfs:subClassOf* P:OCSE_Entity.
        }}
        """
        )
        qsrc = context["query"] = request.GET.get("query", example_query)

        try:
            ackrep_entities, onto_entities = core.AOM.run_sparql_query_and_translate_result(qsrc)
        except Exception as e:
            context["err"] = f"The following error occurred: {str(e)}"
            ackrep_entities, onto_entities = [], []

        context["ackrep_entities"] = ackrep_entities
        context["onto_entities"] = onto_entities
        context["c"] = util.Container()  # this could be used for further options

        return TemplateResponse(request, "ackrep_web/search_sparql.html", context)


class NotYetImplementedView(View):
    def get(self, request):
        context = {}

        return TemplateResponse(request, "ackrep_web/not_yet_implemented.html", context)


def _create_source_code_links(entity):
    try:
        repo = Repo(core.data_path)
    except InvalidGitRepositoryError():
        assert False, f"The directory {core.data_path} is not a git repository!"

    links = []

    base_url = repo.remote().url
    branch_name = repo.active_branch.name
    rel_code_path = entity.base_path.replace("\\", "/").split("ackrep_data")[-1]
    links.append(base_url.split(".git")[0] + "/tree/" + branch_name + "/" + rel_code_path)

    return links
    
def _get_source_code(entity):
    c = core.Container()
    abs_base_path = os.path.join(core.root_path, entity.base_path)
    c.object_list = []

    for i, file in enumerate(os.listdir(abs_base_path)):
        if ".py" in file:
            c.object_list.append(core.Container())
            py_path = os.path.join(abs_base_path, file)
            py_file = open(py_path)

            c.object_list[-1].source_code = py_file.read()
            c.object_list[-1].file_name= file
            c.object_list[-1].id = "python_code_" + str(i)

            py_file.close()

    return c

