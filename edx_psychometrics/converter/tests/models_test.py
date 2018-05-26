import unittest
from collections import OrderedDict

from .utils import FakeAnswers, FakeCourse
import models as t


class NormalizersTest(unittest.TestCase):
    def test_normalize_url(self):
        func = t.normalize_module_url

        self.assertEqual(
            func('module://chapter/block/'), 'module://chapter/block/')
        self.assertEqual(
            func('module://chapter/block/?qq'), 'module://chapter/block/')
        self.assertEqual(
            func('module://chapter/block/#tt'), 'module://chapter/block/')
        self.assertEqual(
            func('module://chapter/block/?q=x&t'), 'module://chapter/block/')
        self.assertEqual(
            func('module://chapter/block'), 'module://chapter/')

    def test_get_module_id(self):
        self.assertEqual(t.get_module_id('module://chapter/block/'), 'chapter')


class UsersTest(unittest.TestCase):
    def setUp(self):
        self.users = t.Users()

    def test_tasks(self):
        self.users.post_solution('u1', 'p1', 't1')
        self.users.score_task('u1', 'p1', 's11', '0')
        self.users.post_solution('u1', 'p1', 't2')
        self.users.score_task('u1', 'p1', 's11', '1')
        self.users.post_solution('u1', 'p1', 't3')
        self.users.score_task('u1', 'p1', 's12', '1')
        self.users.score_task('u1', 'p2', 's21', '1')

        self.assertDictEqual(self.users.submits, {
            'u1': {
                's11': [('t1', 0), ('t2', 1)],
                's12': [('t3', 1)],
                's21': [(None, 1)]
            }
        })

    def test_assessments(self):
        self.users.create_submission('s1', '100', 'p1')
        self.users.assess('s1', '123', '1', '12')
        self.users.assess('s1', '123', '10', '12')
        self.users.assess('s1', '124', '6', '12')

        self.assertDictEqual(self.users.pr_submits, {'s1': ('100', 'p1')})
        self.assertDictEqual(self.users.assessments, {
            's1': [
                ('123', '1', '12'),
                ('123', '10', '12'),
                ('124', '6', '12')
            ]})

    def test_content(self):
        self.users.view_content('u1', 'v1')
        self.users.view_content('u1', 'v2')
        self.users.view_content('u2', 'v1')
        self.users.view_content('u1', 'v1')
        self.users.view_content('u2', 'v3')

        self.assertDictEqual(self.users.viewed_content, {
            'u1': {'v1', 'v2'}, 'u2': {'v1', 'v3'}
        })

    def test_update(self):
        self.users.post_solution('u1', 'p1', '01.01.2018 12:00:00')
        self.users.score_task('u1', 'p1', 's12', '1')
        self.users.update_data(FakeCourse(), FakeAnswers([
            ('p1', 's12', '', 'u1', '2018-01-01T12:00:00.0000', '1'),
            ('p1', 's11', '', 'u1', '2018-01-01T12:10:00.0000', '0'),
            ('p1', 's11', '', 'u2', '2018-01-01T12:20:00.0000', '1')
        ]))

        self.assertDictEqual(self.users.submits, {
            'u1': {
                's11': [('01.01.2018 12:10:00', 0)],
                's12': [('01.01.2018 12:00:00', 1)]
            },
            'u2': {'s11': [('01.01.2018 12:20:00', 1)]}
        })


class TasksTest(unittest.TestCase):
    def setUp(self):
        self.tasks = t.Tasks()

    def test_add_task(self):
        self.tasks.add_task('p1', 's11', 't 1.1', 'type')
        self.tasks.add_task('p1', 's12', 't 1.2', 'type')
        self.tasks.add_task('p2', 's21', 't 2.1', 'type  2')
        self.tasks.add_task('p2', 's21', 't 2.1', 'type 2')
        self.tasks.add_task('p1', 's11', '', '')
        self.tasks.add_task('p1', 's12', '', '')

        self.assertDictEqual(
            self.tasks.tasks, {'p1': {'s11', 's12'}, 'p2': {'s21'}})
        self.assertDictEqual(
            self.tasks.subtask_text, {
                's11': 't 1.1', 's12': 't 1.2', 's21': 't 2.1'
            })
        self.assertDictEqual(
            self.tasks.subtask_type, {
                's11': 'type',
                's12': 'type',
                's21': 'type 2'
            })

    def test_add_assessment(self):
        self.tasks.add_assessment('p1', 'A 1')
        self.tasks.add_assessment('p2', 'a 2')
        self.tasks.add_assessment('p1', '')

        self.assertDictEqual(
            self.tasks.assessments, {'p1': 'A 1', 'p2': 'a 2'})

    def test_update(self):
        self.tasks.add_task('p1', 's11', 't 1.1', 'type')
        self.tasks.update_data(FakeCourse(), FakeAnswers([
            ('p1', 's11', 'task 1.1', 'answer 1'),
            ('p1', 's12', 'task 1.2', 'answer 2'),
            ('p2', 's21', 'task 2.1', 'answer 3'),
            ('p1', 's12', 'task 1.2', 'answer')
        ]))

        self.assertDictEqual(
            self.tasks.tasks, {'p1': {'s11', 's12'}, 'p2': {'s21'}})
        self.assertDictEqual(
            self.tasks.subtask_text, {
                's11': 't 1.1', 's12': 'task 1.2', 's21': 'task 2.1'
            })
        self.assertDictEqual(
            self.tasks.subtask_type, {
                's11': 'type',
                's12': 'NA',
                's21': 'NA'
            })


class ModulesTest(unittest.TestCase):
    def setUp(self):
        self.modules = t.Modules()

    def test_add_task(self):
        self.modules.add_task('module://chapter/module/?qq', 'p1')
        self.modules.add_task('module://chapter2/module/?qq', 'p2')
        self.modules.add_task('module', 'p3', False)

        self.assertDictEqual(self.modules.tasks, {
            'p1': 'chapter', 'p2': 'chapter2', 'p3': 'module'})
        self.assertDictEqual(self.modules.content, {})

    def test_add_content(self):
        self.modules.add_content('module://chapter/module/?qq', 't1')
        self.modules.add_content('module://chapter2/module/?qq', 't2')
        self.modules.add_content('module', 't3', False)

        self.assertDictEqual(self.modules.tasks, {})
        self.assertDictEqual(self.modules.content, {
            't1': 'chapter', 't2': 'chapter2', 't3': 'module'})

    def test_update(self):
        self.modules.add_task(
            'module://chapter/mod/?q', 'type@problem+block@p1')
        self.modules.add_task('module', 'type@problem+block@p3', False)
        self.modules.add_content(
            'module://chapter/mod/?q', 'type@video+block@t1')
        self.modules.add_content('module', 'type@video+block@t3', False)
        self.modules.update_data(FakeCourse(
            modules=OrderedDict([
                ('chapter', 'Module 1'),
                ('chapter2', 'Тема 2'),
                ('module', 'About')
            ]),
            content={
                'type@problem+block@p2': 'chapter2',
                'type@video+block@t2': 'chapter2'
            }), FakeAnswers())

        self.assertEqual(
            self.modules.get_task_module('type@problem+block@p1'),
            ('chapter', 1, 'Module 1'))
        self.assertEqual(
            self.modules.get_task_module('type@problem+block@p2'),
            ('chapter2', 2, 'Тема 2'))
        self.assertEqual(
            self.modules.get_task_module('type@problem+block@p3'),
            ('module', 3, 'About'))

        self.assertEqual(
            self.modules.get_content_module('type@video+block@t1'),
            ('chapter', 1, 'Module 1'))
        self.assertEqual(
            self.modules.get_content_module('type@video+block@t2'),
            ('chapter2', 2, 'Тема 2'))
        self.assertEqual(
            self.modules.get_content_module('type@video+block@t3'),
            ('module', 3, 'About'))


class ContentTest(unittest.TestCase):
    def setUp(self):
        self.content = t.Content()

    def test_add(self):
        self.content.add_content('t1', 'id1')
        self.content.add_content('t1', 'id2')
        self.content.add_content('t2', 'id3')
        self.content.add_content('t1', 'id2')
        self.content.add_content('t1', 'id4')
        self.content.add_content('t2', 'id5')

        self.assertDictEqual(
            self.content.content,
            {'t1': {'id1', 'id2', 'id4'}, 't2': {'id3', 'id5'}})

    def test_add_update(self):
        self.content.add_content('video', 'v1')
        self.content.add_content('textbook', 't1')
        self.content.update_data(FakeCourse(content={
            'type@video+block@v1': 'm1',
            'type@video+block@v2': 'm2',
            'type@problem+block@p1': 'm1'
        }), FakeAnswers())

        self.assertDictEqual(
            self.content.content,
            {
                'video': {'v1', 'v2'},
                'textbook': {'t1'}
            })
