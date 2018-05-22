import logging
import re
from collections import OrderedDict
from datetime import datetime
from itertools import chain, izip, izip_longest
from time import time

from lazy import lazy
from pytz import UTC
from six import text_type

from lms.djangoapps.instructor_analytics.csvs import format_dictlist

from lms.djangoapps.grades.context import grading_context, grading_context_for_course
from student.models import CourseEnrollment
from courseware.courses import get_course_by_id
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory

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
        status_interval = 100
        task_progress = TaskProgress(action_name, num_reports, start_time)

        #course
        course = get_course_by_id(course_id)
        graded_scorable_blocks = cls._graded_scorable_blocks_to_header(course)

        # Students
        current_step = {'step': 'Calculating Grades'}
        enrolled_students = CourseEnrollment.objects.users_enrolled_in(course_id, include_inactive=True)
        header_row = OrderedDict([('id', 'Student ID'), ('email', 'Email'), ('username', 'Username')])
        rows = [list(header_row.values()) + ['Enrollment Status', 'Grade'] + _flatten(graded_scorable_blocks.values())]
        for student, course_grade, error in CourseGradeFactory().iter(enrolled_students, course):
            student_fields = [getattr(student, field_name) for field_name in header_row]
            task_progress.attempted += 1

            if not course_grade:
                err_msg = text_type(error)
                # There was an error grading this student.
                if not err_msg:
                    err_msg = u'Unknown error'
                task_progress.failed += 1
                continue

            enrollment_status = _user_enrollment_status(student, course_id)

            earned_possible_values = []
            for block_location in graded_scorable_blocks:
                try:
                    problem_score = course_grade.problem_scores[block_location]
                except KeyError:
                    earned_possible_values.append([u'Not Available', u'Not Available'])
                else:
                    if problem_score.first_attempted:
                        earned_possible_values.append([problem_score.earned, problem_score.possible])
                    else:
                        earned_possible_values.append([u'Not Attempted', problem_score.possible])

            rows.append(student_fields + [enrollment_status, course_grade.percent] + _flatten(earned_possible_values))

            task_progress.succeeded += 1
            if task_progress.attempted % status_interval == 0:
                task_progress.update_task_state(extra_meta=current_step)

        current_step = {'step': 'Calculating students answers to problem'}
        log.warning(
            action_name,
            num_reports,
            start_time,
            current_step
        )
        task_progress.update_task_state(extra_meta=current_step)

        # Compute result table and format it
        task_progress.attempted = task_progress.succeeded = len(rows)
        task_progress.skipped = task_progress.total - task_progress.attempted

        # rows.insert(0, header_row)

        current_step = {'step': 'Uploading CSV'}
        task_progress.update_task_state(extra_meta=current_step)

        # Perform the upload
        csv_name = u'psychometrics_report'
        upload_csv_to_report_store(rows, csv_name, course_id, start_date)

    @classmethod
    def _graded_scorable_blocks_to_header(cls, course):
        """
        Returns an OrderedDict that maps a scorable block's id to its
        headers in the final report.
        """
        scorable_blocks_map = OrderedDict()
        grading_context = grading_context_for_course(course)
        for assignment_type_name, subsection_infos in grading_context['all_graded_subsections_by_type'].iteritems():
            for subsection_index, subsection_info in enumerate(subsection_infos, start=1):
                for scorable_block in subsection_info['scored_descendants']:
                    header_name = (
                        u"{assignment_type} {subsection_index}: "
                        u"{subsection_name} - {scorable_block_name}"
                    ).format(
                        scorable_block_name=scorable_block.display_name,
                        assignment_type=assignment_type_name,
                        subsection_index=subsection_index,
                        subsection_name=subsection_info['subsection_block'].display_name,
                    )
                    scorable_blocks_map[scorable_block.location] = [header_name + " (Earned)",
                                                                    header_name + " (Possible)"]

        return scorable_blocks_map

        return task_progress.update_task_state(extra_meta=current_step)
