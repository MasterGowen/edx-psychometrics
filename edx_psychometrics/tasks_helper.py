import logging
import re
from collections import OrderedDict
from datetime import datetime
from itertools import chain, izip, izip_longest
from time import time

from lazy import lazy
import pytz
from pytz import UTC
from six import text_type
import json

from lms.djangoapps.instructor_analytics.csvs import format_dictlist

from lms.djangoapps.grades.context import grading_context, grading_context_for_course
from lms.djangoapps.course_blocks.utils import get_student_module_as_dict
from student.models import CourseEnrollment
from courseware.courses import get_course_by_id
from opaque_keys.edx.keys import CourseKey, UsageKey
from xmodule.modulestore.django import modulestore
from openedx.core.djangoapps.content.block_structure.manager import BlockStructureManager
from openedx.core.djangoapps.content.block_structure.api import get_block_structure_manager

from xmodule.modulestore.inheritance import own_metadata

from openedx.core.djangoapps.content.course_structures.models import CourseStructure

from courseware.user_state_client import DjangoXBlockUserStateClient
from lms.djangoapps.grades.course_grade_factory import CourseGradeFactory

from courseware.models import StudentModule
from django.conf import settings
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

        # CSV2
        current_step = {'step': 'Calculating CSV2'}
        cls._get_csv2_data(course_id, enrolled_students, start_date, "psychometrics_report_csv2")
        task_progress.update_task_state(extra_meta=current_step)

        # CSV3
        current_step = {'step': 'Calculating CSV3'}
        cls._get_csv3_data(course_id, enrolled_students, start_date, "psychometrics_report_csv3")
        task_progress.update_task_state(extra_meta=current_step)

        # Perform the upload
        # csv_name = u'psychometrics_report'
        # upload_csv_to_report_store(rows, csv_name, course_id, start_date)

        return task_progress.update_task_state(extra_meta=current_step)

    @classmethod
    def _get_csv1_data(cls, course_id, enrolled_students, start_date, csv_name):
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
        upload_csv_to_report_store(rows, csv_name, course_id, start_date)

    @classmethod
    def _get_csv2_data(cls, course_id, enrolled_students, start_date, csv_name):
        course = get_course_by_id(course_id)
        headers = ('user_id', 'item_id', 'correct', 'time')
        rows = []

        for student, course_grade, error in CourseGradeFactory().iter(enrolled_students, course):
            student_modules = StudentModule.objects.filter(
                student=student,
                course_id=course_id,
                module_type='problem'
            )

        structure = CourseStructure.objects.get(course_id=course_id).ordered_blocks
        blocks = get_block_structure_manager(CourseKey.from_string(str(course_id))).get_collected()
        # for block in blocks:
        #     rows.append([type(block)]) # ,modulestore().get_item(block)
        # for block in blocks:
        #     try:
        #         # rows.append([modulestore().get_block_original_usage(CourseKey.from_string(str(course_id)))])
        #         rows.append([block])
        #     except Exception as e:
        #         rows.append([str(e)])

        # for key, value in structure.items():
        #     if value["block_type"] == 'problem':
        #         try:
        #             log.debug()
        #             rows.append([
        #                 key,
        #                 value,
        #                 str(modulestore().get_item(UsageKey.from_string(key)))
        #
        #
        #             ])
        #         except Exception as e:
        #             rows.append([str(e)])

        for block in blocks:
            try:
                rows.append([block])
            except Exception as e:
                rows.append([str(e)])
        # for name, field in block.fields.items():
        #     try:
        #         rows.append((name, field.read_from(block)))
        #     except:
        #         pass

        # for key, value in structure.items():
        #     if value["block_type"] == 'problem':
        #
        #
        #         rows.append([
        #             key,
        #             value,
        #             # get_student_module_as_dict()
        #
        #         ])

        # for s in student_modules:
        #     rows.append([
        #         s,
        #         1,
        #     ])

        # rows.insert(0, headers)
        upload_csv_to_report_store(rows, csv_name, course_id, start_date)

    @classmethod
    def _get_csv3_data(cls, course_id, enrolled_students, start_date, csv_name):
        user_state_client = DjangoXBlockUserStateClient()
        course = modulestore().get_course(course_id, depth=5, nav_depth=5)
        # headers = ('user_id', 'content_piece_id', 'viewed', 'p')
        rows = []
        structure = CourseStructure.objects.get(course_id=course_id).ordered_blocks
        blocks = get_block_structure_manager(CourseKey.from_string(str(course_id))).get_collected()

        problem_set = []
        problem_info = {}
        for section in course.get_children():
            c_subsection = 0
            for subsection in section.get_children():
                c_subsection += 1
                c_unit = 0
                for unit in subsection.get_children():
                    c_unit += 1
                    c_problem = 0
                    for child in unit.get_children():
                        if child.location.block_type == 'problem':
                            c_problem += 1
                            problem_set.append(child.location)
                            problem_info[child.location] = {
                                'id': text_type(child.location),
                                'x_value': "P{0}.{1}.{2}".format(c_subsection, c_unit, c_problem),
                                'display_name': own_metadata(child).get('display_name', ''),
                                'inputs': str(dir(child)),
                            }

        # for student, course_grade, error in CourseGradeFactory().iter(enrolled_students, course):
        #     student_modules = StudentModule.objects.filter(
        #         student=student,
        #         course_id=course_id,
        #         # module_type='html'
        #     )
        for i in problem_info.keys():
            rows.append([problem_info[i][e] for e in problem_info[i].keys()])

        # for s in student_modules:
        #     try:
        #         history_entries = list(user_state_client.get_history(student.username, s.module_state_key))
        #         for e in history_entries:
        #             try:
        #                 rows.append([
        #                     s.student.id,
        #                     e.module_type,
        #                     e.id,
        #
        #                     e.updated.astimezone(pytz.timezone(settings.TIME_ZONE))
        #                 ])
        #             except:
        #                 pass
        #     except:
        #         pass

        # for b in blocks:
        #     try:
        #         rows.append([str(b)])
        #     except:
        #         pass
        # for s in structure:
        #
        #     try:
        #         rows.append([s])
        #     except:
        #         pass

        # rows.insert(0, headers)
        upload_csv_to_report_store(rows, csv_name, course_id, start_date)

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
