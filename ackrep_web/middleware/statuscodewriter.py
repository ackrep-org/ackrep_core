"""
Custom middleware which passes the http status code to the repo
"""

from ipydex import IPS


class StatusCodeWriterMiddleware(object):

    def __init__(self, get_response):
        self.get_response = get_response
        # One-time configuration and initialization.

    def __call__(self, request):
        # Code to be executed for each request before
        # the view (and before later middleware) are called.

        # this method must be defined for every middleware class
        # we have nothing to do here
        response = self.get_response(request)
        return response

    # noinspection PyMethodMayBeStatic
    def process_template_response(self, request, response):
        """
        Inject the status code of the response into the contex-data. This allows to render it directly to the
        final html (see base.html).

        This hook only works on reponses which are created by a view which finishes with

         `return TemplateResponse(request, "sometemplate.html", context=context)

        :param request:     the request (including the relevant .META attribute)
        :param response:    the response object

        :return:
        """

        response.context_data.update({"http_status_code": response.status_code,
                                     "template_name": response.template_name})

        return response
