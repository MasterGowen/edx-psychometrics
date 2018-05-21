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

from lms.djangoapps.instructor_task.tasks_helper.runner import TaskProgress
from lms.djangoapps.instructor_task.tasks_helper.utils import upload_csv_to_report_store


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
        current_step = {'step': 'Calculating students answers to problem'}
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

        return task_progress.update_task_state(extra_meta=current_step)
