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
import edx_psychometrics

from lms.djangoapps.instructor_task.api_helper import submit_task

log = logging.getLogger(__name__)

TASK_SUBMISSION_OK = 'created'

SUCCESS_MESSAGE_TEMPLATE = _("The {report_type} report is being created. "
                             "To view the status of the report, see Pending Tasks below.")


def submit_get_psychometrics_data(request, course_key):
    """
    AlreadyRunningError is raised if an psychometrics report is already being generated.
    """
    task_type = 'get_psychometrics_data'
    task_class = edx_psychometrics.api.get_psychometrics_data_task
    task_input = {}
    task_key = ''

    return submit_task(request, task_type, task_class, course_key, task_input, task_key)


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
    submit_get_psychometrics_data(request, course_key)
    success_status = SUCCESS_MESSAGE_TEMPLATE.format(report_type=report_type)

    return JsonResponse({"status": success_status})


import logging
from functools import partial

from celery import task
from django.conf import settings
from django.utils.translation import ugettext_noop

from lms.djangoapps.instructor_task.tasks_helper.runner import run_main_task
from lms.djangoapps.instructor_task.tasks_base import BaseInstructorTask

from .tasks_helper import PsychometricsReport

TASK_LOG = logging.getLogger('edx.celery.task')


@task(base=BaseInstructorTask, routing_key=settings.GRADES_DOWNLOAD_ROUTING_KEY)  # pylint: disable=not-callable
def get_psychometrics_data_task(entry_id, xmodule_instance_args):
    """
    Generate psychometrics reports archive.
    """
    action_name = ugettext_noop('get_psychometrics_data')
    task_fn = partial(PsychometricsReport.generate, xmodule_instance_args)
    return run_main_task(entry_id, task_fn, action_name)
