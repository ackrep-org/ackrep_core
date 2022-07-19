import time
from textwrap import dedent as twdd
import pprint
from django.db import OperationalError
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.template.response import TemplateResponse, HttpResponse
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
from ackrep_core.util import run_command
import yaml
import shutil
import hmac
import json
from git import Repo

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

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
        if isinstance(entity, core.models.SystemModel):
            c.pdf_list = core.get_data_files(entity.base_path, endswith_str=".pdf", create_media_links=True)
        c.source_code_link = _create_source_code_link(entity)
        c.source_code_container = _get_source_code(entity)

        if isinstance(entity, (core.models.SystemModel, core.models.ProblemSolution, core.models.Notebook)):
            env_key = entity.compatible_environment
            if env_key == "" or env_key is None:
                env_key = settings.DEFAULT_ENVIRONMENT_KEY
            c.env_name = core.get_entity(env_key).name
            c.env_key = env_key

        # create an object container (entity.oc) where for each string-keys the real object is available
        core.resolve_keys(entity)

        return c

    # noinspection PyMethodMayBeStatic
    def get(self, request, key):
        # inherit cotext data from EntityDetailView like source code and pdf
        c = self.get_context_container(key)

        exitflag = False
        c.result = "pending"
        results_base_path = os.path.join(core.ci_results_path, "history")
        # filter all ci_results yamls and sort them newest to oldest
        filename_list = sorted(filter(lambda item: "ci_results" in item, os.listdir(results_base_path)), reverse=True)
        # iterate all result files
        for i, result_filename in enumerate(filename_list):
            results_path = os.path.join(results_base_path, result_filename)
            with open(results_path) as results_file:
                results = yaml.load(results_file, Loader=yaml.FullLoader)
            # if key is in current file
            if key in results.keys():
                ci_result_entity = results[key]
                # take result of first test encountered (most recent)
                if c.result == "pending":
                    c.ci_result_entity = ci_result_entity
                    c.result = ci_result_entity["result"]
                    c.build_url = results["ci_logs"]["build_url"]
                # entity passed on latest test
                if i == 0 and ci_result_entity["result"] == 0:
                    exitflag = True
                # entity passed on some old test:
                elif i > 0 and ci_result_entity["result"] == 0:
                    c.last_time_passing = ci_result_entity["date"]
                    c.logs = core.Container()
                    c.logs.ackrep_data = results["commit_logs"]["ackrep_data"]
                    c.logs.ackrep_core = results["commit_logs"]["ackrep_core"]
                    c.logs.build_url = results["ci_logs"]["build_url"]
                    c.logs.environment = ci_result_entity["env_version"]

                    exitflag = True
            else:
                core.logger.info(f"Entity {key} is not in {result_filename}.")
            if exitflag:
                break

        if c.result == "pending":
            core.logger.warning(f"Entity {key} not found in any CI result files.")
            c.result = -1

        ## system_model and solution specifics:
        if isinstance(c.entity, (models.ProblemSolution, models.SystemModel)):
            c.image_list = core.get_data_files(f"ackrep_plots/{key}", endswith_str=".png", create_media_links=True)
            # if ci didnt provide image, check fallback image folder
            if len(c.image_list) == 0:
                core.logger.info("No image found, checking fallback repo.")
                c.image_list = core.get_data_files(
                    f"ackrep_fallback_binaries/{key}", endswith_str=".png", create_media_links=True
                )
                c.plot_disclaimer = True

        ## notebook specifics:
        if isinstance(c.entity, models.Notebook):
            nb = core.get_data_files(f"ackrep_notebooks/{key}", endswith_str=".html", create_media_links=True)
            assert len(nb) == 1, "Multiple Notebooks per entity not supportet."
            c.notebook = nb[0]

        c.show_debug = False

        if c.result == 0:
            c.result_css_class = "success"
            c.verbal_result = "Success."
            c.test_date = c.ci_result_entity["date"]
            c.diff_time_str = c.ci_result_entity["runtime"]
        # no major error but numerical result was unexpected
        elif c.result == 2:
            c.result_css_class = "inaccurate"
            c.verbal_result = "Inaccurate. (Different result than expected.)"
            c.test_date = c.ci_result_entity["date"]
            c.issues = c.ci_result_entity["issues"]
            c.diff_time_str = c.ci_result_entity["runtime"]
        # entity did not show in any result file
        elif c.result == -1:
            c.result_css_class = "unknown"
            c.verbal_result = "Unknown. (Entity was not included in any CI Job.)"
        else:
            c.result_css_class = "fail"
            c.verbal_result = "Script Error."
            c.show_debug = settings.DEBUG
            c.test_date = c.ci_result_entity["date"]
            c.issues = c.ci_result_entity["issues"]
            c.diff_time_str = c.ci_result_entity["runtime"]

        context = {"c": c}

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


@method_decorator(csrf_exempt, name="dispatch")
class Webhook(View):
    """get plots and results from CI"""

    # noinspection PyMethodMayBeStatic
    def get(self, request):

        if not settings.DEVMODE:
            res = f"""
            <!DOCTYPE html>
            Enable DEVMODE to look at webhook data.
            """
            return HttpResponse(res, content_type="text/html")

        def recursive_table(d):
            if type(d) == dict:
                res = f""
                for key, value in d.items():
                    res += f"""<tr><td>{key}</td><td>{recursive_table(value)}</td></tr>"""
                return f"""<table>{res}</table>"""
            else:
                return d

        path = os.path.join(core.root_path, "tmp")
        try:
            files = os.listdir(path)
            for file_name in files:
                name, ending = file_name.split(".")
                if ending == "yaml":
                    with open(os.path.join(path, file_name)) as file:
                        results = yaml.load(file, Loader=yaml.FullLoader)
            content = recursive_table(results)
        except FileNotFoundError:
            content = "nothing in the temp folder"

        style = "<style>table, th, td { border: 1px solid black;  border-collapse: collapse; padding: 5px}</style>"
        res = f"""
        <!DOCTYPE html>
        {style}
        <b>Last CI Report</b><br><br>

        {content}
        """

        return HttpResponse(res, content_type="text/html")

    # noinspection PyMethodMayBeStatic
    def post(self, request):
        secret = settings.SECRET_CIRCLECI_WEBHOOK_KEY
        if self.verify_signature(secret, request):
            if request.headers["Circleci-Event-Type"] == "workflow-completed":
                body = json.loads(request.body.decode())

                branch_name = body["pipeline"]["vcs"]["branch"]
                if branch_name == "feature_webhook":
                    IPS()
                elif branch_name == settings.ACKREP_DATA_BRANCH:
                    core.download_and_store_artifacts(branch_name, request)
                else:
                    core.logger.critical(f"No action specified for branch name {branch_name}")
                    IPS()

            elif request.headers["Circleci-Event-Type"] == "ping":
                IPS()
            else:
                core.logger.critical(f"No action specified for event type {request.headers['Circleci-Event-Type']}")
                IPS()

        context = {}
        return TemplateResponse(request, "ackrep_web/webhook.html", context)

    def verify_signature(self, secret, request):
        headers = request.headers
        try:
            body = bytes(request.body, "utf-8")
        except TypeError:
            # body already in bytes
            body = request.body
        try:
            secret = bytes(secret, "utf-8")
        except:
            pass
        # get the v1 signature from the `circleci-signature` header
        signature_from_header = {
            k: v for k, v in [pair.split("=") for pair in headers["circleci-signature"].split(",")]
        }["v1"]

        # Run HMAC-SHA256 on the request body using the configured signing secret
        valid_signature = hmac.new(secret, body, "sha256").hexdigest()

        # use constant time string comparison to prevent timing attacks
        return hmac.compare_digest(valid_signature, signature_from_header)


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


@method_decorator(csrf_exempt, name="dispatch")
class DebugView(View):
    """
    This View serves as simple entrypoint for debugging
    """

    # noinspection PyMethodMayBeStatic
    def get(self, request):
        if not settings.DEBUG:
            return HttpResponse("Debug mode is deactivated", content_type="text/plain")

        import bleach

        IPS()

        output_data = [
            ("settings.CONFIG_PATH", settings.CONFIG_PATH),
            ("settings.LAST_DEPLOYMENT", settings.LAST_DEPLOYMENT),
            ("request", request),
            ("request.headers", request.headers),
            ("request.body", request.body),
        ]

        lines = [
            f"<tr><td>{x}</td><td>&nbsp;</td><td><pre>{bleach.clean(repr(y)).replace(',', ',<br>')}</pre></td></tr>"
            for x, y in output_data
        ]
        line_str = "\n".join(lines)
        res = f"""
        <!DOCTYPE html>
        <b>Debugging page</b><br>
        
        <table>
        {line_str}
        </table>
        """
        core.logger.info(bleach.clean(repr(request.headers)).replace(",", ",\n"))
        core.logger.info(request.body)

        return HttpResponse(res, content_type="text/html")


def _create_source_code_link(entity):
    try:
        repo = Repo(core.data_path)
    except InvalidGitRepositoryError:
        msg = f"The directory {core.data_path} is not a git repository!"
        raise InvalidGitRepositoryError(msg)

    base_url = settings.ACKREP_DATA_BASE_URL
    branch_name = settings.ACKREP_DATA_BRANCH
    rel_code_path = entity.base_path.replace("\\", "/").split("ackrep_data")[-1]
    link = base_url.split(".git")[0] + "/tree/" + branch_name + rel_code_path

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
