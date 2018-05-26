import csv
import logging

import utils


__all__ = ['CourseParser', 'CoursesParser']


class CoursesParser:
    def __init__(self, courses):
        self.courses = {}
        self._parse(courses)

    def _parse(self, courses):
        for (i, item) in enumerate(csv.reader(courses, delimiter=';')):
            if len(item) < 2:
                logging.warning('Invalid line %d in course names file', i)
                continue

            (course_id, course_name) = item
            self.courses[course_id] = course_name

    def __getitem__(self, course_id):
        return self.courses.get(course_id, course_id)


class CourseParser:
    TYPES = ('type@problem', 'type@openassessment', 'type@video')

    def __init__(self, course):
        self.modules = utils.NonEmptyOrderedDict()
        self.content = {}
        self._parse(course)

    def _parse(self, course):
        for (i, item) in enumerate(csv.reader(course, delimiter=';')):
            if len(item) < 2:
                logging.warning('Invalid line %d in course structure file', i)
                continue

            chapter = item[0]
            name = item[-1]
            middle = item[1:-1]
            module_id = utils.get_id(chapter)
            self.modules[module_id] = name.strip()

            for item in middle:
                if any(map(lambda type_: type_ in item, self.TYPES)):
                    self.content[item] = module_id
