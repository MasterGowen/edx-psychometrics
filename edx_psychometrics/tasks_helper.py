import logging
import re
import json
import pytz
from pytz import UTC
from collections import OrderedDict
from datetime import datetime
from itertools import chain
from time import time

from lms.djangoapps.instructor_task.tasks_helper.runner import TaskProgress
from lms.djangoapps.grades.context import grading_context_for_course
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory

from student.models import CourseEnrollment, user_by_anonymous_id
from courseware.models import StudentModule
from courseware.courses import get_course_by_id
from courseware.user_state_client import DjangoXBlockUserStateClient

from opaque_keys.edx.keys import CourseKey, UsageKey
from opaque_keys.edx.locator import BlockUsageLocator
from xmodule.modulestore.django import modulestore

from openedx.core.djangoapps.content.course_structures.models import CourseStructure

# ORA
from openassessment.assessment.models import Assessment

from edx_psychometrics.utils import get_course_item_submissions, _use_read_replica, \
    upload_csv_to_report_store_by_semicolon, upload_json_to_report_store, PsychometricsReportStore

from django.conf import settings

log = logging.getLogger(__name__)


class PsychometricsReport(object):

    arch = PsychometricsReportStore()

    @classmethod
    def generate(cls, _xmodule_instance_args, _entry_id, course_id, task_input, action_name):
        """
        For a given `course_id`, generate a 5 CSV file containing
        information about the learning process
        """
        start_time = time()
        start_date = datetime.now(UTC)
        num_reports = 1
        task_progress = TaskProgress(action_name, num_reports, start_time)

        enrolled_students = CourseEnrollment.objects.users_enrolled_in(course_id, include_inactive=True)

        # Generating Generating CSV1
        current_step = {'step': 'Calculating CSV1'}
        filename_csv1, file_csv1 = cls._get_csv1_data(course_id, enrolled_students, "psychometrics_report_csv1")
        cls.arch.append(filename_csv1, file_csv1)
        task_progress.update_task_state(extra_meta=current_step)

        # Generating CSV2
        current_step = {'step': 'Calculating CSV2'}
        filename_csv2, file_csv2 = cls._get_csv2_data(course_id, "psychometrics_report_csv2")
        cls.arch.append(filename_csv2, file_csv2)
        task_progress.update_task_state(extra_meta=current_step)

        # Generating CSV3
        current_step = {'step': 'Calculating CSV3'}
        filename_csv3, file_csv3 = cls._get_csv3_data(course_id, enrolled_students, "psychometrics_report_csv3")
        cls.arch.append(filename_csv3, file_csv3)
        task_progress.update_task_state(extra_meta=current_step)

        # Generating CSV4
        current_step = {'step': 'Calculating CSV4'}
        filename_csv4, file_csv4 = cls._get_csv4_data(course_id, "psychometrics_report_csv4")
        cls.arch.append(filename_csv4, file_csv4)
        task_progress.update_task_state(extra_meta=current_step)

        # Generating CSV5
        current_step = {'step': 'Calculating CSV5'}
        filename_csv5, file_csv5 = cls._get_csv5_data(course_id, "psychometrics_report_csv5")
        cls.arch.append(filename_csv5, file_csv5)
        task_progress.update_task_state(extra_meta=current_step)

        cls.arch.save_archive(course_id, "archive", start_date)

        # # Generating course description json
        # current_step = {'step': 'Calculating description json'}
        # cls._get_course_json_data(course_id, start_date, "course")
        # task_progress.update_task_state(extra_meta=current_step)

        return task_progress.update_task_state(extra_meta=current_step)

    @classmethod
    def _get_csv1_data(cls, course_id, enrolled_students, csv_name):
        user_state_client = DjangoXBlockUserStateClient()
        course = get_course_by_id(course_id)
        headers = ('user_id', 'item_id', 'correct', 'time')
        rows = []

        for student, course_grade, error in CourseGradeFactory().iter(enrolled_students, course):
            student_modules = StudentModule.objects.filter(
                student=student,
                course_id=course_id,
                module_type='problem'
            )

            for s in student_modules:
                if "correct_map" in s.state:
                    history_entries = list(user_state_client.get_history(student.username, s.module_state_key))
                    for e in history_entries:
                        if "correct_map" in e.state:
                            for item in e.state["correct_map"]:
                                rows.append([
                                    s.student.id,
                                    item,
                                    1 if e.state["correct_map"][item]["correctness"] == "correct" else 0,
                                    e.updated.astimezone(pytz.timezone(settings.TIME_ZONE))
                                ])

        rows.insert(0, headers)
        filename, file = upload_csv_to_report_store_by_semicolon(rows, csv_name)
        return filename, file

    @classmethod
    def _get_csv2_data(cls, course_id, csv_name):
        structure = CourseStructure.objects.get(course_id=course_id).ordered_blocks
        headers = ('item_id', 'item_type', 'item_name', 'module_id', 'module_order', 'module_name')
        datarows = []
        module_order = 0
        for key, value in structure.items():
            if value['block_type'] == 'vertical':
                for block in value['children']:
                    if structure[block]['block_type'] == 'problem':
                        current_block = structure[block]
                        row = [
                            current_block['usage_key'].split("@")[-1],
                            current_block['block_type'],
                            current_block['display_name'],
                            key.split("@")[-1],
                            module_order,
                            value['display_name']
                        ]
                        datarows.append(row)
                module_order = module_order + 1

        datarows.insert(0, headers)
        filename, file = upload_csv_to_report_store_by_semicolon(datarows, csv_name)
        return filename, file

    @classmethod
    def _get_csv3_data(cls, course_id, enrolled_students, csv_name):
        headers = ('user_id', 'content_piece_id', 'viewed', 'p')

        rows = []

        course = get_course_by_id(course_id)
        chapters = [chapter for chapter in course.get_children() if not chapter.hide_from_toc]
        vertical_map = [
            {str(c.location): [  # chapter
                                 {str(s.location): [str(t.location) for t in s.get_children()  # sequention:
                                                    ]
                                  } for s in c.get_children() if not s.hide_from_toc]
             } for c in chapters]

        def _viewed(c_pos, sequential, vertical, student):
            _sm = StudentModule.objects.filter(module_type='sequential',
                                               course_id=CourseKey.from_string(str(course_id)),
                                               student=student,
                                               module_state_key=BlockUsageLocator.from_string(sequential)
                                               ).first()
            if _sm:
                position = json.loads(_sm.state)["position"]
                rows.append([vertical_map[c_pos][sequential], vertical])

                if vertical_map[c_pos][sequential].index(vertical) <= position:
                    return 1
                else:
                    return 0
            else:
                return 0

        for student in enrolled_students:
            for c_pos, _chapter in enumerate(vertical_map):
                for subsection, sequences in _chapter.items():
                    for s in sequences:
                        for verticals in s.values():
                            for vertical in verticals:
                                rows.append([
                                    student.id,
                                    vertical.split("@")[-1],
                                    _viewed(c_pos, subsection, vertical, student)
                                ])
        rows.insert(0, headers)

        filename, file = upload_csv_to_report_store_by_semicolon(rows, csv_name)
        return filename, file

    @classmethod
    def _get_csv4_data(cls, course_id, csv_name):
        structure = CourseStructure.objects.get(course_id=course_id).ordered_blocks
        headers = (
            'content_piece_id', 'content_piece_type', 'content_piece_name', 'module_id', 'module_order', 'module_name')
        datarows = []
        module_order = 0
        for key, value in structure.items():
            if value['block_type'] == 'vertical':
                for block in value['children']:
                    current_block = structure[block]
                    row = [
                        current_block['usage_key'].split("@")[-1],
                        current_block['block_type'],
                        current_block['display_name'],
                        key.split("@")[-1],
                        module_order,
                        value['display_name']
                    ]
                    datarows.append(row)
                module_order = module_order + 1

        datarows.insert(0, headers)
        filename, file = upload_csv_to_report_store_by_semicolon(datarows, csv_name)
        return filename, file

    @classmethod
    def _get_csv5_data(cls, course_id, csv_name):

        openassessment_blocks = modulestore().get_items(CourseKey.from_string(str(course_id)),
                                                        qualifiers={'category': 'openassessment'})
        rows = []
        for openassessment_block in openassessment_blocks:
            x_block_id = openassessment_block.get_xblock_id()
            all_submission_information = get_course_item_submissions(course_id, x_block_id, 'openassessment')
            for student_item, submission, score in all_submission_information:
                max_score = score.get('points_possible')
                assessments = _use_read_replica(
                    Assessment.objects.prefetch_related('parts').
                        prefetch_related('rubric').
                        filter(
                        submission_uuid=submission['uuid'],
                    )
                )
                for assessment in assessments:
                    scorer_points = 0
                    for part in assessment.parts.order_by('criterion__order_num'):
                        if part.option is not None:
                            scorer_points += part.option.points
                    row = [
                        str(user_by_anonymous_id(str(student_item['student_id'])).id),
                        x_block_id.split("@")[-1],
                        str(user_by_anonymous_id(str(assessment.scorer_id)).id),
                        scorer_points,
                        max_score,
                        # assessment.score_type
                    ]
                    rows.append(row)
        header = [
            'user_id',
            'item_id',
            'scorer_id',
            'score',
            'max_score',
            # 'score_type'
        ]
        datarows = [header] + [row for row in rows]

        filename, file = upload_csv_to_report_store_by_semicolon(datarows, csv_name)
        return filename, file

    @classmethod
    def _get_course_json_data(cls, course_id, csv_name):
        course = CourseKey.from_string(str(course_id))
        course_data = {
            "short_name": "+".join([course.org, course.course, course.run]),
            "long_name": get_course_by_id(CourseKey.from_string(str(course_id))).display_name
        }
        return "course", course_data
        # upload_json_to_report_store(course_data, 'course', course_id, start_date)

    @classmethod
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
