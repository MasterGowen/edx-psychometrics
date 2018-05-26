import abc
import collections
import re

import utils

MODULE_URL = re.compile(r'([^#?]*/)')


def normalize_module_url(url):
    return (MODULE_URL.findall(url) or [''])[0]


def get_module_id(url):
    return list(filter(None, url.split('/')))[-2]


class BaseModel(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def update_data(self, course, answers):
        pass


class Users(BaseModel):
    def __init__(self):
        self.times = collections.defaultdict(
            lambda: collections.defaultdict(list))
        self.submits = collections.defaultdict(
            lambda: collections.defaultdict(list))
        self.pr_submits = {}
        self.assessments = collections.defaultdict(list)
        self.viewed_content = collections.defaultdict(set)

    def post_solution(self, user_id, problem_id, time):
        self.times[user_id][problem_id].append(time)

    def score_task(self, user_id, problem_id, subtask_id, correct, time=None):
        time = (self.times[user_id][problem_id] or [time])[-1]
        self.submits[user_id][subtask_id].append((time, int(correct)))

    def create_submission(self, submission_id, user_id, problem_id):
        self.pr_submits[submission_id] = (user_id, problem_id)

    def assess(self, submission_id, reviewer, score, max_score):
        self.assessments[submission_id].append((reviewer, score, max_score))

    def view_content(self, user_id, content_id):
        self.viewed_content[user_id].add(content_id)

    def update_data(self, course, answers):
        for (taskid, subtaskid, _, userid, time, correct) in answers.answers:
            time = utils.convert_datetime(time)
            if not self.submits[userid][subtaskid]:
                self.post_solution(userid, taskid, time)
                self.score_task(userid, taskid, subtaskid, correct)


class Tasks(BaseModel):
    def __init__(self):
        self.tasks = collections.defaultdict(set)
        self.subtask_text = utils.NonEmptyDict()
        self.subtask_type = utils.NonEmptyDict()
        self.assessments = utils.NonEmptyDict()

    def add_task(self, problem_id, subtask_id, text, type_):
        self.tasks[problem_id].add(subtask_id)
        self.subtask_text[subtask_id] = text
        self.subtask_type[subtask_id] = type_

    def add_assessment(self, problem_id, name):
        self.assessments[problem_id] = name

    def update_data(self, course, answers):
        for (problem_id, subtask_id, text) in [a[0:2] for a in answers.answers]:
            if subtask_id not in self.subtask_text:
                self.add_task(problem_id, subtask_id, text, 'NA')


class Modules(BaseModel):
    def __init__(self):
        self.tasks = utils.NonEmptyDict()
        self.content = utils.NonEmptyDict()
        self.module_index = {}

    def add_task(self, link, problem_id, normalize=True):
        problem_id = utils.get_id(problem_id)
        if normalize:
            link = get_module_id(normalize_module_url(link))
        self.tasks[problem_id] = link

    def add_content(self, link, content_id, normalize=True):
        content_id = utils.get_id(content_id)
        if normalize:
            link = get_module_id(normalize_module_url(link))
        self.content[content_id] = link

    def get_task_module(self, problem_id):
        problem_id = utils.get_id(problem_id)
        if problem_id not in self.tasks:
            return None
        return self.module_index.get(self.tasks[problem_id], None)

    def get_content_module(self, content_id):
        content_id = utils.get_id(content_id)
        if content_id not in self.content:
            return None
        return self.module_index.get(self.content[content_id], None)

    def update_data(self, course, answers):
        for (content_id, module_id) in course.content.items():
            if 'type@problem' in content_id:
                self.add_task(module_id, content_id, False)
            elif 'type@video' in content_id:
                self.add_content(module_id, content_id, False)

        used = set(self.tasks.values()) | set(self.content.values())
        if course.modules:
            for (moduleid, name) in course.modules.items():
                if moduleid in used:
                    self._add_to_index(moduleid, name)
        else:
            for moduleid in used:
                self._add_to_index(moduleid, '')

    def _add_to_index(self, moduleid, name):
        self.module_index[moduleid] = (
            moduleid, len(self.module_index) + 1, name or 'NA')


class Content(BaseModel):
    def __init__(self):
        self.content = collections.defaultdict(set)

    def add_content(self, content_type, content_id):
        self.content[content_type].add(content_id)

    def update_data(self, course, answers):
        for (content_id, _) in course.content.items():
            item_id = utils.get_id(content_id)
            if 'type@video' in content_id:
                self.add_content('video', item_id)
