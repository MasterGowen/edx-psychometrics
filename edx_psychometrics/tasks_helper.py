import json
import logging
from datetime import datetime
from time import time

import pytz
from capa import responsetypes
from courseware.courses import get_course_by_id
from courseware.models import StudentModule
from courseware.user_state_client import DjangoXBlockUserStateClient
from django.conf import settings
from lms.djangoapps.grades.new.course_grade_factory import CourseGradeFactory
from lms.djangoapps.instructor.utils import get_module_for_student
from lms.djangoapps.instructor_task.tasks_helper.runner import TaskProgress
from lxml import etree
from opaque_keys.edx.keys import CourseKey, UsageKey
# ORA
from openassessment.assessment.models import Assessment
from openedx.core.djangoapps.content.course_structures.models import CourseStructure
from pytz import UTC
from student.models import CourseEnrollment, user_by_anonymous_id
from student.roles import CourseInstructorRole, CourseStaffRole
from xmodule.modulestore.django import modulestore

from edx_psychometrics.utils import get_course_item_submissions, _use_read_replica, write_to_csv_by_semicolon, PsychometricsReportStore

log = logging.getLogger(__name__)


class PsychometricsReport(object):
    archive = PsychometricsReportStore()

    @classmethod
    def generate(cls, _xmodule_instance_args, _entry_id, course_id, task_input, action_name):
        """
        For a given `course_id`, generate a 5 CSV files containing
        information about the learning process
        """
        start_time = time()
        start_date = datetime.now(UTC)
        num_reports = 1
        task_progress = TaskProgress(action_name, num_reports, start_time)

        enrolled_students = CourseEnrollment.objects.users_enrolled_in(course_id, include_inactive=True)

        # Generating Generating CSV1
        current_step = {'step': 'Calculating CSV1'}
        file_csv1 = cls._get_csv1_data(course_id, enrolled_students)
        cls.archive.append_csv("csv1", file_csv1)
        task_progress.update_task_state(extra_meta=current_step)

        # Generating CSV2
        current_step = {'step': 'Calculating CSV2'}
        file_csv2 = cls._get_csv2_data(course_id)
        cls.archive.append_csv("csv2", file_csv2)
        task_progress.update_task_state(extra_meta=current_step)

        # Generating CSV3
        current_step = {'step': 'Calculating CSV3'}
        file_csv3 = cls._get_csv3_data(course_id, enrolled_students)
        cls.archive.append_csv("csv3", file_csv3)
        task_progress.update_task_state(extra_meta=current_step)

        # Generating CSV4
        current_step = {'step': 'Calculating CSV4'}
        file_csv4 = cls._get_csv4_data(course_id)
        cls.archive.append_csv("csv4", file_csv4)
        task_progress.update_task_state(extra_meta=current_step)

        # Generating CSV5
        current_step = {'step': 'Calculating CSV5'}
        file_csv5 = cls._get_csv5_data(course_id)
        cls.archive.append_csv("csv5", file_csv5)
        task_progress.update_task_state(extra_meta=current_step)

        # Generating course description json
        current_step = {'step': 'Calculating description json'}
        data_json = cls._get_course_json_data(course_id)
        cls.archive.append_json("course", data_json)
        task_progress.update_task_state(extra_meta=current_step)

        cls.archive.save_archive(course_id, "psychometrics_data", start_date)

        return task_progress.update_task_state(extra_meta=current_step)

    @classmethod
    def _get_csv1_data(cls, course_id, enrolled_students):
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
                if s.state:
                    if "correct_map" in s.state:
                        # try:
                        history_entries = list(user_state_client.get_history(student.username, s.module_state_key))
                        for e in history_entries:
                            if "correct_map" in e.state:
                                for item in e.state["correct_map"]:
                                    rows.append([
                                        s.student.id,
                                        item,
                                        1 if e.state["correct_map"][item]["correctness"] == "correct" else 0,
                                        e.updated.astimezone(pytz.timezone(settings.TIME_ZONE)).strftime(
                                            "%d.%m.%Y %H:%M:%S")
                                    ])
                        # except Exception as e:
                        #     log.info("Get history: " + str(e))

        rows.insert(0, headers)
        file = write_to_csv_by_semicolon(rows)
        return file

    @classmethod
    def _get_csv2_data(cls, course_id):
        structure = CourseStructure.objects.get(course_id=course_id).ordered_blocks
        headers = ('item_id', 'item_type', 'item_name', 'module_id', 'module_order', 'module_name')
        instructors = set(CourseInstructorRole(CourseKey.from_string(str(course_id))).users_with_role())
        # the page only lists staff and assumes they're a superset of instructors. Do a union to ensure.
        user = list(set(CourseStaffRole(CourseKey.from_string(str(course_id))).users_with_role()).union(instructors))[0]

        module_order = 0
        datarows = []
        registered_loncapa_tags = responsetypes.registry.registered_tags()

        chapters = [s for s in structure.values() if s['block_type'] == 'chapter']
        for chapter in chapters:
            sequentials = chapter['children']
            for sequential_id in sequentials:
                sequential = structure[sequential_id]
                for block_id in sequential['children']:
                    block = structure[block_id]
                    for item_id in block['children']:
                        item = structure[item_id]
                        if item['block_type'] == 'problem':
                            try:
                                usage_key = UsageKey.from_string(item['usage_key'])
                                block = get_module_for_student(user, usage_key)
                                state_inputs = block.displayable_items()[0].input_state.keys()
                                loncapa_xml_tree = etree.XML(block.data)
                                response_types = [node.tag for node in loncapa_xml_tree.iter() if
                                                  node.tag in registered_loncapa_tags]
                                if len(state_inputs) > len(response_types):
                                    while len(state_inputs) != len(response_types):
                                        response_types.append(response_types[-1])
                                for idx, input_state in enumerate(state_inputs):
                                    row = [
                                        input_state,
                                        response_types[idx],
                                        item['display_name'],
                                        chapter['usage_key'].split("@")[-1],
                                        module_order,
                                        chapter['display_name']
                                    ]
                                    datarows.append(row)
                            except:
                                pass
                        elif item['block_type'] == 'library_content':
                            for lib_item in item['children']:
                                current_block_lib = structure[lib_item]
                                if current_block_lib['block_type'] == 'problem':
                                    usage_key = UsageKey.from_string(current_block_lib['usage_key'])
                                    block = get_module_for_student(user, usage_key)
                                    state_inputs = block.displayable_items()[0].input_state.keys()
                                    loncapa_xml_tree = etree.XML(block.data)
                                    response_types = [node.tag for node in loncapa_xml_tree.iter() if
                                                      node.tag in registered_loncapa_tags]
                                    for idx, input_state in enumerate(state_inputs):
                                        row = [
                                            input_state,
                                            response_types[idx],
                                            current_block_lib['display_name'],
                                            chapter['usage_key'].split("@")[-1],
                                            module_order,
                                            chapter['display_name']
                                        ]
                                        datarows.append(row)
                        elif item['block_type'] == 'openassessment':
                            row = [
                                item['usage_key'].split("@")[-1],
                                item['block_type'],
                                item['display_name'],
                                chapter['usage_key'].split("@")[-1],
                                module_order,
                                chapter['display_name']
                            ]
                            datarows.append(row)

            module_order = module_order + 1
        datarows.insert(0, headers)
        file = write_to_csv_by_semicolon(datarows)
        return file

    @classmethod
    def _get_csv3_data(cls, course_id, enrolled_students):
        headers = ('user_id', 'content_piece_id', 'viewed', 'subsection')
        structure = CourseStructure.objects.get(course_id=course_id).ordered_blocks

        rows = []

        course = get_course_by_id(course_id)
        chapters = [chapter for chapter in course.get_children() if not chapter.hide_from_toc]
        vertical_map = {}
        for c in chapters:
            for s in c.get_children():
                if not s.hide_from_toc:
                    vertical_map[s.location] = [t.location for t in s.get_children()]

        def _viewed(_subsection, _vertical, _student):
            _sm = StudentModule.objects.filter(student=_student,
                                               module_state_key=_subsection
                                               ).first()
            if _sm:
                position = json.loads(_sm.state)["position"]

                if vertical_map[_subsection].index(_vertical) <= position:
                    return 1
                else:
                    return 0
            else:
                return 0

        for student in enrolled_students:
            for subsection in vertical_map.keys():
                for vertical in vertical_map[subsection]:
                    for block in structure[str(vertical)]["children"]:
                        if "video" in block:
                            rows.append([
                                student.id,
                                str(block).split("@")[-1],
                                _viewed(subsection, vertical, student),
                                str(subsection).split("@")[-1],
                            ])
        rows.insert(0, headers)

        file = write_to_csv_by_semicolon(rows)
        return file

    @classmethod
    def _get_csv4_data(cls, course_id):
        structure = CourseStructure.objects.get(course_id=course_id).ordered_blocks
        headers = (
            'content_piece_id', 'content_piece_type', 'content_piece_name', 'module_id', 'module_order', 'module_name')
        # datarows = []
        # sequentials = [s for s in structure.values() if s['block_type'] == 'sequential']
        # module_order = 0
        # for sequential in sequentials:
        #     for block in sequential['children']:
        #         for item in structure[block]['children']:
        #             row = [
        #                 structure[item]['usage_key'].split("@")[-1],
        #                 structure[item]['block_type'],
        #                 structure[item]['display_name'],
        #                 sequential['usage_key'].split("@")[-1],
        #                 module_order,
        #                 sequential['display_name']
        #             ]
        #             datarows.append(row)
        #     module_order += 1

        datarows = []
        chapters = [s for s in structure.values() if s['block_type'] == 'chapter']
        module_order = 0
        for chapter in chapters:
            for sequential in chapter['children']:
                for block in structure[sequential]['children']:
                    for item in structure[block]['children']:
                        if structure[item]['block_type'] == 'video':  # !!! only video blocks !!!
                            row = [
                                structure[item]['usage_key'].split("@")[-1],
                                structure[item]['block_type'],
                                structure[item]['display_name'],
                                chapter['usage_key'].split("@")[-1],
                                module_order,
                                chapter['display_name']
                            ]
                            datarows.append(row)
            module_order += 1

        datarows.insert(0, headers)
        file = write_to_csv_by_semicolon(datarows)
        return file

    @classmethod
    def _get_csv5_data(cls, course_id):

        openassessment_blocks = modulestore().get_items(CourseKey.from_string(str(course_id)),
                                                        qualifiers={'category': 'openassessment'})
        rows = []
        for openassessment_block in openassessment_blocks:

            # max_score = 0
            # for criterion in openassessment_block.rubric_criteria:
            #     criterion_points = []
            #     for option in criterion['options']:
            #         criterion_points.append(option['points'])
            #     max_score += max(criterion_points)

            x_block_id = openassessment_block.get_xblock_id()
            all_submission_information = get_course_item_submissions(course_id, x_block_id, 'openassessment')
            for student_item, submission, score in all_submission_information:
                # max_score = score.get('points_possible')
                assessments = _use_read_replica(
                    Assessment.objects.prefetch_related('parts').prefetch_related('rubric').filter(
                        submission_uuid=submission['uuid'],
                    )
                )
                for assessment in assessments:
                    scorer_points = 0
                    max_score = int(assessment.points_possible)
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
            'reviewer_id',
            'score',
            'max_score',
            # 'score_type'
        ]
        datarows = [header] + [row for row in rows]

        file = write_to_csv_by_semicolon(datarows)
        return file

    @classmethod
    def _get_course_json_data(cls, course_id):
        course = CourseKey.from_string(str(course_id))
        course_data = {
            "short_name": "+".join([course.org, course.course, course.run]),
            "long_name": get_course_by_id(CourseKey.from_string(str(course_id))).display_name
        }
        return course_data
