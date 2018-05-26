import collections
import csv
import json
import logging
import re

from models import Users, Tasks, Modules, Content
from utils import get_item, get_items, convert_datetime, get_id, Registry


__all__ = ['LogParser']


class LogParser:
    handler = Registry()

    def _update_course(self, item):
        self.course_name = (
            get_item(item, 'context.course_id').split(':', 1)[-1]
            or self.course_name)

    @handler.add(event_type=['load_video', 'edx.video.loaded'])
    def _load_video(self, item):
        self._update_course(item)
        video_id = get_item(json.loads(get_item(item, 'event')), 'id')
        page = get_item(item, 'page')
        self.content.add_content('video', video_id)
        self.modules.add_content(page, video_id)

    @handler.add(event_type=['play_video', 'edx.video.played'])
    def _play_video(self, item):
        self._update_course(item)
        user_id = get_item(item, 'context.user_id')
        video_id = get_item(json.loads(get_item(item, 'event')), 'id')
        self.users.view_content(user_id, video_id)

    @handler.add(event_type='problem_check', event_source='server')
    def _problem_check_server(self, item):
        self._update_course(item)
        (problem_id, user_id, time) = get_items(
            item, ['event.problem_id', 'context.user_id', 'time'])
        subtasks = get_item(item, 'event.submission', type_=dict)
        for (subtask_id, subtask) in subtasks.items():
            (question, task_type) = get_items(
                subtask, ['question', 'response_type'])
            correct = get_item(subtask, 'correct', type_=bool)
            self.tasks.add_task(problem_id, subtask_id, question, task_type)
            self.users.score_task(
                user_id, problem_id, subtask_id, correct, time)

    @handler.add(event_type='edx.grades.problem.submitted')
    def _problem_submitted(self, item):
        self._update_course(item)
        (user_id, problem_id, page, time) = get_items(
            item, ['context.user_id', 'event.problem_id', 'referer', 'time'])
        self.modules.add_task(page, problem_id)
        self.users.post_solution(user_id, problem_id, convert_datetime(time))

    @handler.add(event_type='openassessmentblock.create_submission')
    def _create_submission(self, item):
        self._update_course(item)
        (submission_id, task_id, user_id, name, page) = get_items(
            item, ['event.submission_uuid', 'context.module.usage_key',
                   'context.user_id', 'context.module.display_name',
                   'referer'])
        self.users.create_submission(submission_id, user_id, task_id)
        self.modules.add_task(page, task_id)
        self.tasks.add_assessment(task_id, name)

    @handler.add(event_type=['openassessmentblock.self_assess',
                             'openassessmentblock.peer_assess',
                             'openassessmentblock.staff_assess'])
    def _assess_submission(self, item):
        self._update_course(item)
        (submission_id, user_id) = get_items(
            item, ['event.submission_uuid', 'context.user_id'])
        scores = get_item(item, 'event.parts', type_=list)
        points = sum(
            get_item(score, 'option.points', type_=int) for score in scores)
        max_points = sum(
            get_item(score, 'criterion.points_possible', type_=int)
            for score in scores)
        self.users.assess(submission_id, user_id, points, max_points)

    def __init__(self, log, course, answers, courses):
        self.course_name = ''
        self.users = Users()
        self.tasks = Tasks()
        self.modules = Modules()
        self.content = Content()

        self._parse(log)

        for item in (self.users, self.tasks, self.modules, self.content):
            item.update_data(course, answers)

        self.course_long_name = courses[self.course_name]

    def _parse(self, log):
        for (i, line) in enumerate(log):
            try:
                item = json.loads(line.split(':', maxsplit=1)[-1])
                LogParser.handler(self, item)
            except Exception as e:
                logging.warning('Error on process entry, line %d: %s', i, e)

    def get_course_info(self):
        return {
            'short_name': self.course_name,
            'long_name': self.course_long_name
        }

    def get_student_solutions(self, user_id=None):
        if user_id is None:
            for userid in self.users.submits:
                yield self.get_student_solutions(userid)
        else:
            submits = self.users.submits[user_id]
            for (taskid, tries) in submits.items():
                for (time, correct) in tries:
                    yield (user_id, taskid, correct, time)

    def get_student_content(self, user_id=None):
        if user_id is None:
            for userid in self.users.viewed_content:
                yield self.get_student_content(userid)
        else:
            viewed = self.users.viewed_content[user_id]
            for (_, content) in self.content.content.items():
                for content_id in content:
                    if self.modules.get_content_module(content_id):
                        yield (user_id, content_id, int(content_id in viewed))

    def get_assessments(self):
        for submission_id in self.users.pr_submits:
            (user_id, problem_id) = self.users.pr_submits[submission_id]
            problem_id = get_id(problem_id)
            assessments = self.users.assessments[submission_id]
            for (reviewer, score, max_score) in assessments:
                yield (user_id, problem_id, reviewer, score, max_score)

    def get_tasks(self, task_id=None):
        if task_id is None:
            task_ids = set(self.tasks.tasks) | set(self.tasks.assessments)
            for taskid in task_ids:
                yield self.get_tasks(taskid)
        else:
            module = self.modules.get_task_module(task_id)
            if not module:
                return
            if task_id in self.tasks.tasks:
                for subtask in self.tasks.tasks[task_id]:
                    text = self.tasks.subtask_text.get(subtask) or 'NA'
                    yield (subtask, self.tasks.subtask_type[subtask],
                           text, module)
            if task_id in self.tasks.assessments:
                name = self.tasks.assessments[task_id] or 'NA'
                yield (get_id(task_id), 'openassessment', name, module)

    def get_content(self):
        for (content_type, content) in self.content.content.items():
            for content_id in content:
                module = self.modules.get_content_module(content_id)
                if module:
                    yield (content_id, content_type, 'NA', module)
