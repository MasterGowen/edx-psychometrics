import logging


from django.db import IntegrityError, transaction
from django.utils.translation import ugettext as _
from django.views.decorators.cache import cache_control
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.http import require_http_methods, require_POST

from opaque_keys import InvalidKeyError
from opaque_keys.edx.keys import CourseKey, UsageKey
from util.json_request import JsonResponse
from lms.djangoapps.instructor.views.api import require_level, common_exceptions_400



log = logging.getLogger(__name__)

TASK_SUBMISSION_OK = 'created'

SUCCESS_MESSAGE_TEMPLATE = _("The {report_type} report is being created. "
                             "To view the status of the report, see Pending Tasks below.")



@transaction.non_atomic_requests
@require_POST
@ensure_csrf_cookie
@cache_control(no_cache=True, no_store=True, must_revalidate=True)
@require_level('staff')
@common_exceptions_400
def get_psychometrics_data(request, course_id):
    """
    Pushes a Celery task which will aggregate psychometrics data.
    """
    course_key = CourseKey.from_string(course_id)
    report_type = _('get_psychometrics_data')
    lms.djangoapps.instructor_task.api.submit_get_psychometrics_data(request, course_key)  #TODO: replace dych
    success_status = SUCCESS_MESSAGE_TEMPLATE.format(report_type=report_type)

    return JsonResponse({"status": success_status})