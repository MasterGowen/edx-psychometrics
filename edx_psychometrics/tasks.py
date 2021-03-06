import logging
from functools import partial

from celery import task
from django.conf import settings
from django.utils.translation import ugettext_noop

from lms.djangoapps.instructor_task.tasks_helper.runner import run_main_task
from lms.djangoapps.instructor_task.tasks_base import BaseInstructorTask

from .tasks_helper import PsychometricsReport, ViewsReport, EnrollmentsReport

TASK_LOG = logging.getLogger('edx.celery.task')


@task(base=BaseInstructorTask, routing_key=settings.GRADES_DOWNLOAD_ROUTING_KEY)  # pylint: disable=not-callable
def get_psychometrics_data(entry_id, xmodule_instance_args):
    """
    Generate psychometrics reports archive.
    """
    action_name = ugettext_noop('get_psychometrics_data')
    task_fn = partial(PsychometricsReport.generate, xmodule_instance_args)
    return run_main_task(entry_id, task_fn, action_name)


@task(base=BaseInstructorTask, routing_key=settings.GRADES_DOWNLOAD_ROUTING_KEY)
def get_views_data(entry_id, xmodule_instance_args):
    """
    Generate views reports archive.
    """
    action_name = ugettext_noop('get_views_data')
    task_fn = partial(ViewsReport.generate, xmodule_instance_args)
    return run_main_task(entry_id, task_fn, action_name)


@task(base=BaseInstructorTask, routing_key=settings.GRADES_DOWNLOAD_ROUTING_KEY)
def get_enrollments_data(entry_id, xmodule_instance_args):
    """
    Generate enrollments reports report.
    """
    action_name = ugettext_noop('get_enrollments_data')
    task_fn = partial(EnrollmentsReport.generate, xmodule_instance_args)
    return run_main_task(entry_id, task_fn, action_name)
