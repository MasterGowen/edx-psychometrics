import unittest

import course as t


class CourseParserTest(unittest.TestCase):
    DATA = """
type@chapter+block@m2;type@sequential+block@s2;type@html+block@h1;Module 2
type@chapter+block@m3;type@sequential+block@s3;type@openassessment+block@a1;Module 3
type@chapter+block@m1;type@sequential+block@s1;type@video+block@v1;Module 1
type@chapter+block@m1;type@sequential+block@s1;type@video+block@v2;Module 1
type@chapter+block@m1;type@sequential+block@s1;type@problem+block@p1;
type@chapter+block@m4;type@sequential+block@s4;type@vertical+block@V1;type@problem+block@p2;Модуль 4
""".strip().split('\n')

    def test_parser(self):
        courses = t.CourseParser(self.DATA)

        self.assertListEqual(
            list(courses.modules.items()),
            [('m2', 'Module 2'), ('m3', 'Module 3'),
             ('m1', 'Module 1'), ('m4', 'Модуль 4')])
        self.assertDictEqual(
            courses.content,
            {
                'type@openassessment+block@a1': 'm3',
                'type@problem+block@p1': 'm1',
                'type@problem+block@p2': 'm4',
                'type@video+block@v1': 'm1',
                'type@video+block@v2': 'm1'
            })
