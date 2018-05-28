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
from student.models import CourseEnrollment, user_by_anonymous_id
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

# ORA
from openassessment.assessment.models import Assessment
from submissions import api as sub_api
# from student.models import user_by_anonymous_id

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
        # cls._get_csv1_data(course_id, enrolled_students, start_date, "psychometrics_report_csv1")
        # task_progress.update_task_state(extra_meta=current_step)

        # CSV2
        current_step = {'step': 'Calculating CSV2'}
        # cls._get_csv2_data(course_id, enrolled_students, start_date, "psychometrics_report_csv2")
        # task_progress.update_task_state(extra_meta=current_step)

        # CSV3
        current_step = {'step': 'Calculating CSV3'}
        cls._get_csv3_data(course_id, enrolled_students, start_date, "psychometrics_report_csv3")
        task_progress.update_task_state(extra_meta=current_step)

        # CSV4

        # CSV5
        current_step = {'step': 'Calculating CSV5'}
        cls._get_csv5_data(course_id, start_date, "psychometrics_report_csv5")
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

        for key, value in structure.items():
            if value["block_type"] == 'problem':
                descriptor = modulestore().get_item(UsageKey.from_string(key))
                parent_metadata = descriptor.xblock_kvs._fields.copy()
                try:
                    # log.debug()
                    rows.append([
                        key,
                        value,
                        str(dir(parent_metadata))

                    ])
                except Exception as e:
                    rows.append([str(e)])

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
        headers = ('user_id', 'content_piece_id', 'viewed', 'p')

        rows = []
        structure = CourseStructure.objects.get(course_id=course_id).ordered_blocks

        vertical_map = {}

        for key, value in structure.items():
            if value["block_type"] == 'vertical':
                try:
                    parent = value['parent']
                    # rows.append([str(parent), value["usage_key"]])
                    if parent not in vertical_map.keys():
                        vertical_map[str(parent)] = [value["usage_key"]]
                    else:
                        vertical_map[str(parent)].append(value["usage_key"])
                except Exception as e:
                    pass

        def _viewed(_vert):
            _sms = StudentModule.objects.filter(module_type='sequential',
                                                course_id=CourseKey.from_string(str(course_id)),
                                                student=student
                                                )
            for _sm in _sms:
                sequential = str(_sm.module_state_key)
                try:
                    rows.append([sequential, _sm.state["position"],  _vert, json.dumps(vertical_map)])
                except:
                    pass
                try:
                    if _vert in vertical_map[sequential]:

                        if vertical_map[sequential].index(_vert) <= _sm.state["position"]:
                            return 1
                except Exception as e:
                    pass

                else:
                    return 0

        for student in enrolled_students:
            for vert in [v for vlist in vertical_map.values() for v in vlist]:
                rows.append([
                    student.id,
                    vert.split("@")[-1],
                    _viewed(vert)
                ])
        # rows += [[s[1].student.id, s[1].state, str(s[1].module_state_key)] for s in sms]

        #
        # problem_set = []
        # problem_info = {}
        # for section in course.get_children():
        #     c_subsection = 0
        #     for subsection in section.get_children():
        #         c_subsection += 1
        #         c_unit = 0
        #         for unit in subsection.get_children():
        #             c_unit += 1
        #             c_problem = 0
        #             for child in unit.get_children():
        #                 # if child.location.block_type == 'problem':
        #                 c_problem += 1
        #                 problem_set.append(child.location)
        #                 problem_info[child.location] = {
        #                     'id': text_type(child.location),
        #                     'x_value': "P{0}.{1}.{2}".format(c_subsection, c_unit, c_problem),
        #                     'display_name': str((own_metadata(child))),  # .get('display_name', ''),
        #                     # 'inputs': str(child.get_state_for_lcp()),
        #                     "type": type(child)
        #                 }

        # for student, course_grade, error in CourseGradeFactory().iter(enrolled_students, course):
        #     student_modules = StudentModule.objects.filter(
        #         student=student,
        #         course_id=course_id,
        #         # module_type='html'
        #     )
        # for i in problem_info.keys():
        #     rows.append([problem_info[i][e] for e in problem_info[i].keys()])
        # for b in blocks:
        #     rows.append(str(b))

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

        rows.insert(0, headers)
        upload_csv_to_report_store(rows, csv_name, course_id, start_date)

    @classmethod
    def _get_csv5_data(cls, course_id, start_date, csv_name):

        openassessment_blocks = modulestore().get_items(CourseKey.from_string(str(course_id)),
                                                        qualifiers={'category': 'openassessment'})

        datarows = []

        for openassessment_block in openassessment_blocks:
            x_block_id = openassessment_block.get_xblock_id()
            all_submission_information = sub_api.get_all_submissions(course_id, x_block_id, 'openassessment')
            for student_item, submission, score in all_submission_information:
                row = []
                assessments = cls._use_read_replica(
                    Assessment.objects.prefetch_related('parts').
                        prefetch_related('rubric').
                        filter(
                        submission_uuid=submission['uuid']
                    )
                )
                assessments_cell = cls._build_assessments_cell(assessments)
                assessments_parts_cell = cls._build_assessments_parts_cell(assessments)
                feedback_options_cell = cls._build_feedback_options_cell(assessments)

                row = [
                    x_block_id,
                    submission['uuid'],
                    submission['student_item'],
                    student_item['student_id'],
                    submission['submitted_at'],
                    submission['answer'],
                    assessments_cell,
                    assessments_parts_cell,
                    score.get('created_at', ''),
                    score.get('points_earned', ''),
                    score.get('points_possible', ''),
                    feedback_options_cell,
                    user_by_anonymous_id(student_item['student_id'])
                ]
                datarows.append(row)

        header = [
            'task_id',
            'Submission ID',
            'Item ID',
            'Anonymized Student ID',
            'Date/Time Response Submitted',
            'Response',
            'Assessment Details',
            'Assessment Scores',
            'Date/Time Final Score Given',
            'Final Score Points Earned',
            'Final Score Points Possible',
            'Feedback Statements Selected',
            'username'
        ]
        rows = [header] + [row for row in datarows]

        upload_csv_to_report_store(rows, csv_name, course_id, start_date)

    @classmethod
    def _use_read_replica(self, queryset):
        """
        Use the read replica if it's available.
        Args:
            queryset (QuerySet)
        Returns:
            QuerySet
        """
        return (
            queryset.using("read_replica")
            if "read_replica" in settings.DATABASES
            else queryset
        )

    @classmethod
    def _build_assessments_cell(cls, assessments):
        """
        Args:
            assessments (QuerySet) - assessments that we would like to collate into one column.
        Returns:
            string that should be included in the 'assessments' column for this set of assessments' row
        """
        returned_string = u""
        for assessment in assessments:
            returned_string += u"Assessment #{}\n".format(assessment.id)
            returned_string += u"-- scored_at: {}\n".format(assessment.scored_at)
            returned_string += u"-- type: {}\n".format(assessment.score_type)
            returned_string += u"-- scorer_id: {}\n".format(assessment.scorer_id)
            if assessment.feedback != u"":
                returned_string += u"-- overall_feedback: {}\n".format(assessment.feedback)
        return returned_string

    @classmethod
    def _build_assessments_parts_cell(cls, assessments):
        """
        Args:
            assessments (QuerySet) - assessments containing the parts that we would like to collate into one column.
        Returns:
            string that should be included in the relevant 'assessments_parts' column for this set of assessments' row
        """
        returned_string = u""
        for assessment in assessments:
            returned_string += u"Assessment #{}\n".format(assessment.id)
            for part in assessment.parts.order_by('criterion__order_num'):
                returned_string += u"-- {}".format(part.criterion.label)
                if part.option is not None and part.option.label is not None:
                    option_label = part.option.label
                    returned_string += u": {option_label} ({option_points})\n".format(
                        option_label=option_label, option_points=part.option.points
                    )
                if part.feedback != u"":
                    returned_string += u"-- feedback: {}\n".format(part.feedback)
        return returned_string

    @classmethod
    def _build_feedback_options_cell(cls, assessments):
        """
        Args:
            assessments (QuerySet) - assessment that we would like to use to fetch and read the feedback options.
        Returns:
            string that should be included in the relevant 'feedback_options' column for this set of assessments' row
        """

        returned_string = u""
        for assessment in assessments:
            for feedback in assessment.assessment_feedback.all():
                for option in feedback.options.all():
                    returned_string += option.text + u"\n"

        return returned_string

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
