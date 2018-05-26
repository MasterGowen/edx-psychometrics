import abc
import contextlib
import csv
import json
import logging
import operator
import os.path

__all__ = ['process_all_csvs']


class BaseProcessor(metaclass=abc.ABCMeta):
    def __init__(self, filename, encoding):
        self._file = open(filename, mode='w', encoding=encoding)

    @abc.abstractmethod
    def process(self, parser):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self._file.close()


class BaseCSVProcessor(BaseProcessor):
    COLUMNS = []

    def __init__(self, prefix, index, encoding):
        super(BaseCSVProcessor, self).__init__('{}{}.csv'.format(prefix, index), encoding)
        self._csv = csv.writer(self._file, delimiter=';')
        self._csv.writerow(map(operator.itemgetter(0), self.COLUMNS))

    def write(self, *items):
        row = tuple(map(str, items))
        for (item, (name, checker)) in zip(row, self.COLUMNS):
            if not checker(item):
                logging.warning('Invalid item "%s" in %s. Skip', name, row)
                return
        self._csv.writerow(row)

    def writeiter(self, iterable):
        for item in iterable:
            self.write(*item)


class Checkers:
    @staticmethod
    def nonempty(value):
        return bool(value)

    @staticmethod
    def non_empty_or_none(value):
        return bool(value) and value != 'None'

    @staticmethod
    def zero_or_one(value):
        return str(value) in ('0', '1')

    @staticmethod
    def positive_int(value):
        with contextlib.suppress(ValueError):
            return int(value) > 0
        return False

    @staticmethod
    def nonnegative_int(value):
        with contextlib.suppress(ValueError):
            return int(value) >= 0
        return False


class Items:
    USER_ID = ('user_id', Checkers.nonempty)
    REVIEWER_ID = ('reviewer_id', Checkers.nonempty)

    ITEM_ID = ('item_id', Checkers.nonempty)
    ITEM_TYPE = ('item_type', Checkers.nonempty)
    ITEM_NAME = ('item_name', Checkers.nonempty)

    CONTENT_ID = ('content_piece_id', Checkers.nonempty)
    CONTENT_TYPE = ('content_piece_type', Checkers.nonempty)
    CONTENT_NAME = ('content_piece_name', Checkers.nonempty)

    MODULE_ID = ('module_id', Checkers.nonempty)
    MODULE_ORDER = ('module_order', Checkers.positive_int)
    MODULE_NAME = ('module_name', Checkers.nonempty)

    SCORE = ('score', Checkers.nonnegative_int)
    MAX_SCORE = ('max_score', Checkers.positive_int)

    CORRECT = ('correct', Checkers.zero_or_one)
    VIEWED = ('viewed', Checkers.zero_or_one)
    TIME = ('time', Checkers.non_empty_or_none)


class CSV1(BaseCSVProcessor):
    COLUMNS = [
        Items.USER_ID, Items.ITEM_ID, Items.CORRECT, Items.TIME]

    def __init__(self, prefix, encoding):
        super(CSV1, self).__init__(prefix, 1, encoding)

    def process(self, parser):
        self.writeiter(parser.get_student_solutions())


class CSV2(BaseCSVProcessor):
    COLUMNS = [
        Items.ITEM_ID, Items.ITEM_TYPE, Items.ITEM_NAME,
        Items.MODULE_ID, Items.MODULE_ORDER, Items.MODULE_NAME]

    def __init__(self, prefix, encoding):
        super(CSV2, self).__init__(prefix, 2, encoding)

    def process(self, parser):
        self.writeiter(parser.get_tasks())


class CSV3(BaseCSVProcessor):
    COLUMNS = [Items.USER_ID, Items.CONTENT_ID, Items.VIEWED]

    def __init__(self, prefix, encoding):
        super(CSV3, self).__init__(prefix, 3, encoding)

    def process(self, parser):
        self.writeiter(parser.get_student_content())


class CSV4(BaseCSVProcessor):
    COLUMNS = [
        Items.CONTENT_ID, Items.CONTENT_TYPE, Items.CONTENT_NAME,
        Items.MODULE_ID, Items.MODULE_ORDER, Items.MODULE_NAME]

    def __init__(self, prefix, encoding):
        super(CSV4, self).__init__(prefix, 4, encoding)

    def process(self, parser):
        self.writeiter(parser.get_content())


class CSV5(BaseCSVProcessor):
    COLUMNS = [
        Items.USER_ID, Items.ITEM_ID, Items.REVIEWER_ID,
        Items.SCORE, Items.MAX_SCORE]

    def __init__(self, prefix, encoding):
        super(CSV5, self).__init__(prefix, 5, encoding)

    def process(self, parser):
        self.writeiter(parser.get_assessments())


class CourseInfoJSON(BaseProcessor):
    def __init__(self, prefix, encoding):
        super(CourseInfoJSON, self).__init__(
            os.path.join(os.path.dirname(prefix), 'course.json'), encoding)

    def process(self, parser):
        json.dump(parser.get_course_info(), self._file)


def process_all_csvs(prefix, encoding, parser):
    for processor in (CSV1, CSV2, CSV3, CSV4, CSV5, CourseInfoJSON):
        with processor(prefix, encoding) as p:
            p.process(parser)
