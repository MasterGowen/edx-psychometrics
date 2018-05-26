import collections
from datetime import datetime


def get_id(edx_id):
    return edx_id.split('@')[-1]


def get_item(data, item, *, type_=str):
    if '.' in item:
        (name, rest) = item.split('.', maxsplit=1)
        return get_item(data.get(name, {}), rest, type_=type_)

    return type_(data.get(item, type_()))


def get_items(data, items, *, type_=str):
    return list(map(lambda item: get_item(data, item, type_=type_), items))


def convert_datetime(timestr):
    return datetime.strptime(
        timestr.split('.')[0].split('+')[0],
        '%Y-%m-%dT%H:%M:%S').strftime('%d.%m.%Y %H:%M:%S')


def iscollection(type_):
    return isinstance(type_, (tuple, list, set, frozenset))


class NonEmptyMixin:
    def __setitem__(self, key, value):
        if value or (key not in self):
            super().__setitem__(key, value)


class NonEmptyDict(NonEmptyMixin, dict):
    pass


class NonEmptyOrderedDict(NonEmptyMixin, collections.OrderedDict):
    pass


class Registry:
    _NULL = object()

    def __init__(self):
        self.handlers = []
        self.default = lambda obj, item: None

    def add(self, **kwargs):
        def wrapper(func):
            if kwargs:
                self.handlers.append(({
                    key: (value if iscollection(value) else [value])
                    for (key, value) in kwargs.items()
                }, func))
            else:
                self.default = func
            return func
        return wrapper

    @staticmethod
    def check_item(item, kwargs):
        for (key, values) in kwargs.items():
            if item.get(key, Registry._NULL) not in values:
                return False
        return True

    def __call__(self, obj, item):
        for (kwargs, func) in self.handlers:
            if Registry.check_item(item, kwargs):
                return func(obj, item)
        return self.default(obj, item)
