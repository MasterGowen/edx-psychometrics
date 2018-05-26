#!/usr/bin/env python3

import argparse
import os.path
import sys

from course import CourseParser, CoursesParser
from answers import AnswersParser
from logs import LogParser
from csv5 import process_all_csvs


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '-e', '--encoding', type=str, default='utf8', help='Files encoding')
    parser.add_argument(
        '-l', '--logs', type=str, required=True, help='Log file')
    parser.add_argument(
        '-c', '--course', type=str, help='Course structure file')
    parser.add_argument(
        '-a', '--answers', type=str, help='Student answers file')
    parser.add_argument(
        '-C', '--courses', type=str, help='Course names file')
    parser.add_argument('output', type=str, help='Output csv prefix')
    return parser.parse_args()


def main():
    params = parse_args()

    optional_data_source = [
        (params.course, CourseParser),
        (params.answers, AnswersParser),
        (params.courses, CoursesParser)]

    optional_source = []
    for (filename, parser) in optional_data_source:
        if filename:
            with open(filename, encoding=params.encoding) as file:
                optional_source.append(parser(file))
        else:
            optional_source.append(parser([]))

    with open(params.logs, encoding=params.encoding) as logfile:
        parser = LogParser(logfile, *optional_source)

    if os.path.isdir(params.output):
        params.output = os.path.join(params.output, 'csv')

    process_all_csvs(
        params.output, params.encoding, parser)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as e:
        # print(e, file=sys.stderr)
        sys.exit(1)
