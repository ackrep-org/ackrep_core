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
import pandas as pd

from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator

# noinspection PyUnresolvedReferences
from ipydex import IPS, activate_ips_on_exception

if not os.environ.get("ACKREP_ENVIRONMENT_NAME"):
    # this env var is set in Dockerfile of env
    import pyerk as p


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

        c.is_executable_entity = isinstance(
            entity, (core.models.SystemModel, core.models.ProblemSolution, core.models.Notebook)
        )

        if c.is_executable_entity:
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

        if c.is_executable_entity:
            exitflag = False
            c.result = "pending"
            results_base_path = os.path.join(core.ci_results_path, "history")
            # filter all ci_results yamls and sort them newest to oldest
            filename_list = sorted(
                filter(lambda item: "ci_results" in item, os.listdir(results_base_path)), reverse=True
            )
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
                c.image_list = sorted(
                    core.get_data_files(f"ackrep_plots/{key}", endswith_str=".png", create_media_links=True)
                )
                # if ci didnt provide image, check fallback image folder
                if len(c.image_list) == 0:
                    core.logger.info("No image found, checking fallback repo.")
                    c.image_list = sorted(
                        core.get_data_files(
                            f"ackrep_fallback_binaries/{key}", endswith_str=".png", create_media_links=True
                        )
                    )
                    c.fallback_disclaimer = True

            ## notebook specifics:
            if isinstance(c.entity, models.Notebook):
                nb = core.get_data_files(f"ackrep_notebooks/{key}", endswith_str=".html", create_media_links=True)
                if len(nb) == 0:
                    core.logger.info("No notebook found, checking fallback repo.")
                    nb = core.get_data_files(
                        f"ackrep_fallback_binaries/{key}", endswith_str=".html", create_media_links=True
                    )
                    c.fallback_disclaimer = True
                assert len(nb) == 1, "No notebook html found."
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

        path = os.path.join(core.ci_results_path, "history")
        try:
            file_name = sorted(os.listdir(path), reverse=True)[0]
            name, ending = file_name.split(".")
            if ending == "yaml":
                with open(os.path.join(path, file_name)) as file:
                    results = yaml.load(file, Loader=yaml.FullLoader)
            content = recursive_table(results)
        except Exception as e:
            content = str(e)

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
                    core.download_and_store_artifacts(branch_name)
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
        PREFIX : <{p.rdfstack.ERK_URI}>
        PREFIX ocse: <erk:/ocse/0.2#>
        SELECT ?s
        WHERE {{
            ?s :R16__has_property ocse:I7733__time_invariance.

        }}
        """
        )
        qsrc = context["query"] = request.GET.get("query", example_query)

        try:
            ackrep_entities, onto_entities = core.AOM.run_sparql_query_and_translate_result(qsrc)
        except Exception as e:
            context["err"] = f"The following error occurred: {str(e)}"
            ackrep_entities, onto_entities = [], []

        onto_entities_no_dupl = hide_duplicate_sparql_res(onto_entities)

        context["ackrep_entities"] = ackrep_entities
        context["onto_entities"] = onto_entities
        context["onto_entities_no_dupl"] = onto_entities_no_dupl
        context["c"] = util.Container()  # this could be used for further options

        return TemplateResponse(request, "ackrep_web/search_sparql.html", context)


def hide_duplicate_sparql_res(res: list) -> list:
    new_list = []
    for entry in res:
        if not entry in new_list:
            new_list.append(entry)
    return new_list


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


class EntityOverView(View):
    """display all results of all ci runs
    entity name | key   | <buildnumbers>
    lorenz      | UXMFA | F | S | S
    """

    def get(self, request):
        table_dict = {}
        build_urls = {}
        # number of table columns on the left containing entity infos (key, name)
        NUM_ENTITY_COLS = 2
        NUM_DISPLAYED_RUNS = 20

        entity_list_list = [
            list(models.ProblemSolution.objects.all()),
            list(models.SystemModel.objects.all()),
            list(models.Notebook.objects.all()),
        ]
        entity_list = [x for xs in entity_list_list for x in xs]

        for e in entity_list:
            table_dict[e.key] = {}
            table_dict[e.key]["Key"] = e.key
            table_dict[e.key]["Name"] = e.name

        results_base_path = os.path.join(core.ci_results_path, "history")
        # filter all ci_results yamls and sort them oldest to newest
        filename_list = sorted(filter(lambda item: "ci_results" in item, os.listdir(results_base_path)))
        # iterate all result files
        for i, result_filename in enumerate(filename_list[-NUM_DISPLAYED_RUNS:]):
            results_path = os.path.join(results_base_path, result_filename)
            with open(results_path) as results_file:
                results = yaml.load(results_file, Loader=yaml.FullLoader)

            for key, value in results.items():
                if len(key) == 5:
                    bn = int(results["ci_logs"]["build_number"])
                    build_urls[bn] = results["ci_logs"]["build_url"]
                    # try except for old keys that are not currently in database
                    try:
                        table_dict[key][bn] = int(value["result"])
                    except KeyError:
                        pass

        # show 0 or 1 instead of 0.0, 1.0
        pd.options.display.float_format = "{:,.0f}".format
        dataframe = pd.DataFrame.from_dict(table_dict, orient="index")
        # add numerical index
        dataframe = dataframe.set_index(np.arange(dataframe.shape[0]))

        # deal with NAN in df
        dataframe["Name"] = dataframe["Name"].replace(np.nan, "<i>not in database</i>")
        dataframe = dataframe.fillna("")

        # add link to entity
        for i, key in enumerate(dataframe["Key"]):
            link = f"""<a href="/e/{key}" title="Checkout Entity">{key}</a>"""
            dataframe.loc[i, "Key"] = link

        # split df and sort builds part by build number
        df_entity_part = dataframe.iloc[:, :NUM_ENTITY_COLS]
        df_builds_part = dataframe.iloc[:, NUM_ENTITY_COLS:]
        df_sorted = df_builds_part.reindex(sorted(df_builds_part.columns), axis=1)
        dataframe_sorted = pd.concat([df_entity_part, df_sorted], axis=1)

        # cell highlighting
        dataframe_sorted = dataframe_sorted.replace([0, 1, 2], ["Pass", "Fail", "Inac"])

        def highlight(cell_value):
            color_0 = "background-color: hsl(120, 60%, 30%);"
            color_1 = "background-color: hsl(0, 90%, 45%);"
            color_2 = "background-color: hsl(34, 90%, 45%);"
            default = ""

            if cell_value == "Pass":
                return color_0
            elif cell_value == "Fail":
                return color_1
            elif cell_value == "Inac":
                return color_2
            return default

        dataframe_sorted = dataframe_sorted.style.applymap(highlight)

        # convert to html
        table_string = dataframe_sorted.to_html()

        # add build urls
        for key in build_urls.keys():
            link = f"""<a title="checkout CI build" href="{build_urls[key]}">{key}</a>"""
            table_string = table_string.replace(str(key), link)

        # rework headers
        num_build_cols = dataframe.shape[1] - NUM_ENTITY_COLS
        row = f"""
            <thead>
            <tr>
                <th colspan="{NUM_ENTITY_COLS + 1}">Entity</th>
                <th colspan="{num_build_cols}">Build</th>
            </tr>"""
        # Note entity_cols + 1 since index col is also displayed in table
        table_string = table_string.replace("<thead>", row)

        # add intermediate headers for entity types
        for i in range(len(entity_list_list)):
            if i == 0:
                """header is inserted BEFORE the nth occurence of the string (here <tr>).
                n = 3, we want to start inserting at 3rd row
                Entity       | Build
                Key   | Name | <build numbers>
                solutions ---------------
                <key> | ..."""
                n = 3
            else:
                # n = 3 headers + len entities before + new rows inserted previously by this loop
                n += len(entity_list_list[i - 1]) + 1
            header = f"""
            <tr>
                <td colspan="{NUM_ENTITY_COLS + 1}"><b>{entity_list_list[i][0].type.replace("_", " ")}s</b></th>
                <td colspan="{num_build_cols}"></th>
            </tr>
            """
            pos = util.find_nth(table_string, "<tr>", n)
            table_string = table_string[:pos] + header + table_string[pos:]

        # TODO: improve sticky header: see
        # TODO: https://stackoverflow.com/questions/54444642/sticky-header-table-with-mutiple-lines-in-the-thead
        # TODO: for orientation
        # styling, linebreaks
        style = """
        <style>
            table {
                border-bottom: 1px Solid Black;
                border-right: 1px Solid Black;
                border-collapse : collapse;
                padding: 5px;
            }
            table td, table th {
                border-left: 1px Solid Black;
                border-top: 1px Solid Black;
                border-bottom:none;
                border-right:none;
                max-width: 400px;
                word-wrap: break-word;
                padding: 5px;
                background-clip: padding-box; /* fixes issue with disappearing borders due to background color*/
            }
            table thead {
                position: sticky;
                top: 54;
                z-index: 2;
            }
            table  th,
            table  tr td {
                background-color: #FFF;
                border: 1px solid black;
                padding: 5px;
            }
        </style>"""

        # put it all together
        res = f"""
        <!DOCTYPE html>
        {style}
        <h2>Entity Overview</h2>
        <br>
        <b>Overview of the last {NUM_DISPLAYED_RUNS} CI jobs.</b>
        <br><br>

        {table_string}
        """

        base_path = os.path.join(core.root_path, "ackrep_core/ackrep_web/templates/ackrep_web/_temp")
        os.makedirs(base_path, exist_ok=True)
        path = os.path.join(base_path, "table.html")
        with open(path, "w") as html_file:
            html_file.write(res)

        context = {}
        return TemplateResponse(request, "ackrep_web/entity_overview.html", context)


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
