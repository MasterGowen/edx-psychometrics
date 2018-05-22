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

from lms.djangoapps.instructor_task.tasks_helper.runner import TaskProgress
from lms.djangoapps.instructor_task.tasks_helper.utils import upload_csv_to_report_store

log = logging.getLogger(__name__)


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

        #Students
        enrolled_students = CourseEnrollment.objects.users_enrolled_in(course_id, include_inactive=True)
        header_row = OrderedDict([('id', 'Student ID'), ('email', 'Email'), ('username', 'Username')])
        log.warning(enrolled_students)



        task_progress = TaskProgress(action_name, num_reports, start_time)
        current_step = {'step': 'Calculating students answers to problem'}
        log.warning(
            action_name,
            num_reports,
            start_time,
            current_step
        )
        task_progress.update_task_state(extra_meta=current_step)

        # Compute result table and format it
        student_data = [
            {
                'label1': 'value-1,1',
                'label2': 'value-1,2',
                'label3': 'value-1,3',
                'label4': 'value-1,4',
            },
            {
                'label1': 'value-2,1',
                'label2': 'value-2,2',
                'label3': 'value-2,3',
                'label4': 'value-2,4',
            }
        ]
        features = ['label1', 'label4']
        header, rows = format_dictlist(student_data, features)

        task_progress.attempted = task_progress.succeeded = len(rows)
        task_progress.skipped = task_progress.total - task_progress.attempted

        rows.insert(0, header)

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
