import unittest

import answers as t


class AnswersParserTest(unittest.TestCase):
    DATA = """
1;course-fall;type@problem+block@aa;aa_1;1234;user;2018.03.03T11:00:00;0;NULL;answer;12;Вопрос;2018.03.03T13:00:00
2;course-fall;type@problem+block@aa;aa_1;1234;user;2018.03.03T12:00:00;1;NULL;Ответ;14;Вопрос;2018.03.03T13:00:30
3;course-fall;type@problem+block@aa;aa_2;1234;user;2018.03.03T12:10:00;0;NULL;qqqq;6;NULL;2018.03.03T13:00:40
4;course-fall;type@problem+block@bb;bb_1;2345;uzer;2018.03.04T12:00:00;1;NULL;YYY;99;XXX;2018.04.04T13:00:50
""".strip().split('\n')

    def test_parser(self):
        answers = t.AnswersParser(self.DATA)
        self.assertListEqual(
            answers.answers,
            [('type@problem+block@aa', 'aa_1', 'Вопрос', '1234',
              '2018.03.03T11:00:00', '0'),
             ('type@problem+block@aa', 'aa_1', 'Вопрос', '1234',
              '2018.03.03T12:00:00', '1'),
             ('type@problem+block@aa', 'aa_2', '', '1234',
              '2018.03.03T12:10:00', '0'),
             ('type@problem+block@bb', 'bb_1', 'XXX', '2345',
              '2018.03.04T12:00:00', '1')])
