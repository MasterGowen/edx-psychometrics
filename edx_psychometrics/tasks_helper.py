import logging
import re
from collections import OrderedDict
from datetime import datetime
from itertools import chain, izip, izip_longest
from time import time

from lazy import lazy
from pytz import UTC
from six import text_type
import json

from lms.djangoapps.instructor_analytics.csvs import format_dictlist

from lms.djangoapps.grades.context import grading_context, grading_context_for_course
from student.models import CourseEnrollment
from courseware.courses import get_course_by_id
from opaque_keys.edx.keys import CourseKey, UsageKey
from courseware.user_state_client import DjangoXBlockUserStateClient
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory

from courseware.models import StudentModule
from lms.djangoapps.instructor_task.tasks_helper.runner import TaskProgress
from lms.djangoapps.instructor_task.tasks_helper.utils import upload_csv_to_report_store

log = logging.getLogger(__name__)

ENROLLED_IN_COURSE = 'enrolled'

NOT_ENROLLED_IN_COURSE = 'unenrolled'


def _user_enrollment_status(user, course_id):
    """
    Returns the enrollment activation status in the given course
    for the given user.
    """
    enrollment_is_active = CourseEnrollment.enrollment_mode_for_user(user, course_id)[1]
    if enrollment_is_active:
        return ENROLLED_IN_COURSE
    return NOT_ENROLLED_IN_COURSE


def _flatten(iterable):
    return list(chain.from_iterable(iterable))


class PsychometricsReport(object):
    @classmethod
    def generate(cls, _xmodule_instance_args, _entry_id, course_id, task_input, action_name):
        """
        For a given `course_id`, generate a CSV file containing
        all student answers to a given problem, and store using a `ReportStore`.
        """
        start_time = time()
        start_date = datetime.now(UTC)
        num_reports = 1
        task_progress = TaskProgress(action_name, num_reports, start_time)

        enrolled_students = CourseEnrollment.objects.users_enrolled_in(course_id, include_inactive=True)

        # CSV1
        current_step = {'step': 'Calculating CSV1'}
        cls._get_csv1_data(course_id, enrolled_students, start_date, "psychometrics_report_csv1")
        task_progress.update_task_state(extra_meta=current_step)

        current_step = {'step': 'LOL'}
        task_progress.update_task_state(extra_meta=current_step)

        # Perform the upload
        # csv_name = u'psychometrics_report'
        # upload_csv_to_report_store(rows, csv_name, course_id, start_date)
        return task_progress.update_task_state(extra_meta=current_step)

    @classmethod
    def _get_csv1_data(cls, course_id, enrolled_students, start_date, csv_name):
        course = get_course_by_id(course_id)

        rows = []

        for student, course_grade, error in CourseGradeFactory().iter(enrolled_students, course):
            student_modules = StudentModule.objects.filter(
                student=student,
                course_id=course_id,
                module_type='problem'
            )
            for s in student_modules:
                if "correct_map" in s.state:
                    correct_map = json.loads(s.state)["correct_map"]
                    for item in correct_map:
                        rows.append([
                            s.student.id,
                            item,
                            1 if correct_map[item]["correctness"] == "correct" else 0,
                            json.loads(s.state)["last_submission_time"]
                        ])



        #         usage_key = UsageKey.from_string(location)
        #         user_state_client = DjangoXBlockUserStateClient()
        #         try:
        #             history_entries += list(user_state_client.get_history(student.username, usage_key))
        #         except DjangoXBlockUserStateClient.DoesNotExist:
        #             pass
        # log.warning([str(e) for e in history_entries])
        upload_csv_to_report_store(rows, csv_name, course_id, start_date)

    @ classmethod
    def _graded_scorable_blocks_to_header(cls, course):
        """
        Returns an OrderedDict that maps a scorable block's id to its
        headers in the final report.
        """
        scorable_blocks_map = []
        grading_context = grading_context_for_course(course)
        for assignment_type_name, subsection_infos in grading_context['all_graded_subsections_by_type'].iteritems():
            for subsection_index, subsection_info in enumerate(subsection_infos, start=1):
                for scorable_block in subsection_info['scored_descendants']:
                    scorable_blocks_map.append(scorable_block.location)
        return scorable_blocks_map
