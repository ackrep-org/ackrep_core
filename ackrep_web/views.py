from fileinput import filename
import time
from textwrap import dedent as twdd
import pprint
from django.db import OperationalError
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
from ackrep_core.models import ActiveJobs
from ackrep_core.util import run_command
import yaml

from ackrep_web.celery import app
import subprocess
from celery.result import AsyncResult
import kombu

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
    def get_context_container(self, key):
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
        c.source_code_link = _create_source_code_link(entity)
        c.source_code_container = _get_source_code(entity)

        # create an object container (entity.oc) where for each string-keys the real object is available
        core.resolve_keys(entity)

        return c

    # noinspection PyMethodMayBeStatic
    def get(self, request, key):
        c = self.get_context_container(key)
        context = {"c": c}

        return TemplateResponse(request, "ackrep_web/entity_detail.html", context)


class CheckView(EntityDetailView):
    def get(self, request, key):
        # inherit cotext data from EntityDetailView like source code and pdf
        c = self.get_context_container(key)

        if type(c.entity) == models.ProblemSolution:
            c.view_type = "check-solution"
            c.view_type_title = "Check Solution for:"

        elif type(c.entity) == models.SystemModel:
            c.view_type = "check-system-model"
            c.view_type_title = "Simulation for:"

        exitflag = False
        c.result = "pending"
        # filter all ci_results yamls and sort them newest to oldest
        filename_list = sorted(filter(lambda item: "ci_results" in item, os.listdir("../ackrep_ci_results")), reverse=True)
        for i, result_filename in enumerate(filename_list):
            results_path = os.path.join(core.root_path, "ackrep_ci_results", result_filename)
            with open(results_path) as results_file:
                results = yaml.load(results_file, Loader=yaml.FullLoader)
            if key in results.keys():
                ci_result_entity = results[key]
                # take result of first test encountered (most recent)
                if c.result == "pending":
                    c.result = ci_result_entity["result"]
                # entity passed on latest test
                if i == 0 and ci_result_entity["result"] == 0:
                    exitflag = True
                # entity passed on some old test:
                if i > 0 and ci_result_entity["result"] == 0:
                    c.last_time_passing = ci_result_entity["date"]
                    exitflag = True
            else:
                core.logger.info(f"Entity {key} is not in {result_filename}.")
            if exitflag: break
        
        if c.result == "pending":
            core.logger.warning(f"Entity {key} not found in any CI result files.")
            c.result = -1

        # c.image_list = core.get_data_files(c.entity.base_path, endswith_str=".png", create_media_links=True)

        c.show_debug = False

        if c.result == 0:
            c.result_css_class = "success"
            c.verbal_result = "Success."
            c.test_data = ci_result_entity["date"]
            c.diff_time_str = ci_result_entity["runtime"]
        # no major error but numerical result was unexpected
        elif c.result == 2:
            c.result_css_class = "inaccurate"
            c.verbal_result = "Inaccurate. (Different result than expected.)"
            c.test_data = ci_result_entity["date"]
            c.issues = ci_result_entity["issues"]
            c.diff_time_str = ci_result_entity["runtime"]
        elif c.result == -1:
            c.result_css_class = "unknown"
            c.verbal_result = "Unknown. (Entity was not included in latest CI Job.)"
        else:
            c.result_css_class = "fail"
            c.verbal_result = "Script Error."
            c.show_debug = settings.DEBUG
            c.test_data = ci_result_entity["date"]
            c.issues = ci_result_entity["issues"]
            c.diff_time_str = ci_result_entity["runtime"]

        context = {"c": c}
        # create an object container (entity.oc) where for each string-key the real object is available
        # _purge_old_jobs()
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


class NewCiResultView(View):

    # noinspection PyMethodMayBeStatic
    def get(self, request):
        # assert os.environ.get("CIRCLE_TOKEN") is not None, "CIRCLE_TOKEN Env Var not set"
        save_cwd = os.getcwd()
        path = os.path.join(core.root_path, "ackrep_ci_results")
        if not os.path.isdir(path):
            os.mkdir(path)
        os.chdir(path)

        cmd = [
            """curl -H 'Circle-Token: $CIRCLE_TOKEN' \
        https://circleci.com/api/v1.1/project/github/ackrep-org/ackrep_data/latest/artifacts \
        | grep -o 'https://[^"]*' \
        | wget --verbose --header 'Circle-Token: $CIRCLE_TOKEN' --input-file -"""
        ]
        # print(cmd)
        res = subprocess.run(cmd, shell=True, text=True, capture_output=True)
        assert res.returncode == 0, "Unable to collect results from circleci."
        str1 = b'\xe2\x80\x98'.decode('utf-8')
        str2 = b'\xe2\x80\x99'.decode('utf-8')
        file_name = res.stderr.split("Saving to: ")[-1].split("\n\n")[0].split(str1)[-1].split(str2)[0]

        with open(file_name) as file:
            results = yaml.load(file, Loader=yaml.FullLoader)

        os.chdir(save_cwd)

        context = {"results": results}

        return TemplateResponse(request, "ackrep_web/new_ci_result.html", context)

    # def post(self, request):
    #     title = request.POST.get("title", "")
    #     repo_url = request.POST.get("repo_url", "")
    #     description = request.POST.get("description", "")

    #     try:
    #         mr = core.create_merge_request(repo_url, title, description)

    #         return redirect("merge-request", key=mr.key)
    #     except Exception as e:
    #         error_str = str(e)
    #         messages.error(request, f"An error occurred: {error_str}")

    #         return redirect("new-merge-request")


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


def _create_source_code_link(entity):
    try:
        repo = Repo(core.data_path)
    except InvalidGitRepositoryError:
        msg = f"The directory {core.data_path} is not a git repository!"
        raise InvalidGitRepositoryError(msg)

    base_url = settings.ACKREP_DATA_BASE_URL
    branch_name = settings.ACKREP_DATA_BRANCH
    rel_code_path = entity.base_path.replace("\\", "/").split("ackrep_data")[-1]
    link = base_url.split(".git")[0] + "/" + branch_name + rel_code_path

    return link


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
            c.object_list[-1].file_name = file
            c.object_list[-1].id = "python_code_" + str(i)

            py_file.close()

    return c


def _get_active_job_by_key(key):
    """queries the database for active jobs with the given key. if none are found, None is returned. If exactly one is
    found, this job is returned. Otherwise an error is rasied.
    :return: tuple (key, celery_id)"""
    active_job_list = ActiveJobs.objects.filter(key=key).values()
    if len(active_job_list) == 0:
        active_job = None
    elif len(active_job_list) == 1:
        active_job = active_job_list[0]
    else:
        msg = "There should not be multiple active jobs with the same key. Maybe job adding or removing is bugged."
        assert 1 == 0, msg

    return active_job


def _add_job_to_db(key, celery_id):
    """add an entry to db with key and celery_id"""
    new_entry = ActiveJobs(key=key, celery_id=celery_id, start_time=time.time())
    new_entry.save()
    return 0


def _remove_job_from_db(key):
    """delete db entry with given key"""
    ActiveJobs.objects.filter(key=key).delete()
    return 0


def _purge_old_jobs():
    active_job_list = ActiveJobs.objects.all().values()
    for job in active_job_list:
        if time.time() - job["start_time"] > settings.RESULT_EXPIRATION_TIME:
            _remove_job_from_db(job["key"])
