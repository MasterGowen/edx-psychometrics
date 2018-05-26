import unittest

import utils as t


class UtilsFunctionsTest(unittest.TestCase):
    DATA = {
        'aa': '1',
        'bb': 1,
        'cc': [1],
        'dd': {
            'aa': '2',
            'bb': {
                'cc': {
                    'dd': '3',
                    'ee': {'ff': 4}
                }
            }
        }
    }

    def test_getid(self):
        self.assertEqual(t.get_id('aa'), 'aa')
        self.assertEqual(t.get_id('aa@bb'), 'bb')
        self.assertEqual(t.get_id('aa@bb@cc'), 'cc')

    def test_getitem(self):
        self.assertEqual(t.get_item(self.DATA, 'aa'), '1')
        self.assertEqual(t.get_item(self.DATA, 'aa', type_=int), 1)
        self.assertEqual(t.get_item(self.DATA, 'bb'), '1')
        self.assertEqual(t.get_item(self.DATA, 'cc', type_=list), [1])
        self.assertEqual(t.get_item(self.DATA, 'dd.aa'), '2')
        self.assertEqual(t.get_item(self.DATA, 'dd.bb.cc.dd'), '3')
        self.assertEqual(t.get_item(self.DATA, 'dd.cc'), '')
        self.assertEqual(t.get_item(self.DATA, 'dd.cc', type_=int), 0)

    def test_getitems(self):
        self.assertEqual(t.get_items(self.DATA, ['aa']), ['1'])
        self.assertEqual(t.get_items(
            self.DATA, ['aa', 'bb'], type_=int), [1, 1])
        self.assertEqual(t.get_items(
            self.DATA, ['aa', 'dd.aa', 'dd.bb.cc.ee.ff']), ['1', '2', '4'])

    def test_convert_datetime(self):
        self.assertEqual(t.convert_datetime('2018-03-03T16:00:14.5678'),
                         '03.03.2018 16:00:14')
        self.assertEqual(t.convert_datetime('2018-03-17T01:59:14.5678+0000'),
                         '17.03.2018 01:59:14')


class NonEmptyDictTests(unittest.TestCase):
    def test_dict(self):
        d = t.NonEmptyDict()
        self.assertDictEqual(d, {})

        d['q'] = 10
        self.assertDictEqual(d, {'q': 10})

        d['q'] = ''
        self.assertDictEqual(d, {'q': 10})

        d['x'] = ''
        self.assertDictEqual(d, {'q': 10, 'x': ''})

        d['x'] = 20
        self.assertDictEqual(d, {'q': 10, 'x': 20})

        d['x'] = ''
        self.assertDictEqual(d, {'q': 10, 'x': 20})


class RegistryTests(unittest.TestCase):
    registry = t.Registry()

    @registry.add(x=['a', 'b'])
    def handler1(self, item):
        return 1

    @registry.add(x='c', y='a')
    def handler2(self, item):
        return 2

    @registry.add(x={'c', 'd'}, y='b')
    def handler3(self, item):
        return 3

    def test_registry(self):
        self.assertEqual(self.registry(self, {'x': 'a'}), 1)
        self.assertEqual(self.registry(self, {'x': 'b'}), 1)
        self.assertEqual(self.registry(self, {'x': 'c'}), None)
        self.assertEqual(self.registry(self, {'x': 'c', 'y': 'a'}), 2)
        self.assertEqual(self.registry(self, {'x': 'c', 'y': 'b'}), 3)
        self.assertEqual(self.registry(self, {'x': 'd', 'y': 'a'}), None)
        self.assertEqual(self.registry(self, {'x': 'd', 'y': 'b'}), 3)
