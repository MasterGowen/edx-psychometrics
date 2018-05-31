import json
import StringIO
import codecs
import csv

from io import BytesIO
from zipfile import ZipFile

from submissions.models import Submission
from submissions.serializers import (
    SubmissionSerializer, StudentItemSerializer, ScoreSerializer
)

from lms.djangoapps.instructor_task.models import ReportStore
from lms.djangoapps.instructor_task.tasks_helper.utils import tracker_emit

from django.conf import settings
from django.core.files.storage import get_valid_filename
from django.core.files.base import ContentFile


class InMemoryZipFile(object):
    def __init__(self):
        self.inMemoryOutputFile = BytesIO()

    def write(self, inzipfilename, data):
        zip = ZipFile(self.inMemoryOutputFile, 'a')
        zip.writestr(inzipfilename, data)
        zip.close()

    def read(self):
        self.inMemoryOutputFile.seek(0)
        return self.inMemoryOutputFile


class PsychometricsReportStore(object):
    def __init__(self):
        self.archive = InMemoryZipFile()

    def append_csv(self, filename, output_buffer):
        self.archive.write(str(filename), output_buffer.read())

    def append_json(self, filename, data):
        self.archive.write(str(filename), json.dumps(data))

    def save_archive(self, course_id, filename, timestamp, config_name='GRADES_DOWNLOAD'):
        report_store = ReportStore.from_config(config_name)
        zip_file_name = u"{filename}_{course}_{timestamp_str}.zip".format(
            filename=filename,
            course=get_valid_filename(unicode("_").join([course_id.org, course_id.course, course_id.run])),
            timestamp_str=timestamp.strftime("%Y-%m-%d-%H%M")
        )
        report_store.store(course_id, zip_file_name, self.archive.read())


def upload_csv_to_report_store_by_semicolon(rows, filename):
    tracker_emit(filename)
    output_buffer = ContentFile('')
    output_buffer.write(codecs.BOM_UTF8)
    csvwriter = csv.writer(output_buffer, delimiter=';')
    csvwriter.writerows(_get_utf8_encoded_rows(rows))
    output_buffer.seek(0)
    csv_filename = u"{filename}.csv".format(filename=filename)
    return csv_filename, output_buffer


# def upload_json_to_report_store(json_data, filename, course_id, timestamp, config_name='GRADES_DOWNLOAD'):
#
#     tracker_emit(filename)
#     json_file = StringIO.StringIO()
#     json_file.write(json.dumps(json_data))
#
#     csv_filename = u"{filename}.csv".format(filename=filename)
#
#     return u"{filename}.csv".format(filename), json_data


# def store_json_file(self, course_id, filename, data):
#     json_file = StringIO.StringIO()
#     json_file.write(json.dumps(data))
#     self.store(course_id, filename, json_file)


# def store_rows_by_semicolon(self, course_id, filename, rows):
#     output_buffer = ContentFile('')
#     output_buffer.write(codecs.BOM_UTF8)
#     csvwriter = csv.writer(output_buffer, delimiter=';')
#     csvwriter.writerows(self._get_utf8_encoded_rows(rows))
#     output_buffer.seek(0)

#     self.store(course_id, filename, output_buffer)


def get_course_item_submissions(course_id, item_id, item_type, read_replica=True):
    submission_qs = Submission.objects
    if read_replica:
        submission_qs = _use_read_replica(submission_qs)

    query = submission_qs.select_related('student_item__scoresummary__latest__submission').filter(
        student_item__course_id=course_id,
        student_item__item_type=item_type,
        student_item__item_id=item_id,
    ).iterator()

    for submission in query:
        student_item = submission.student_item
        serialized_score = {}
        if hasattr(student_item, 'scoresummary'):
            latest_score = student_item.scoresummary.latest
            if (not latest_score.is_hidden()) and latest_score.submission.uuid == submission.uuid:
                serialized_score = ScoreSerializer(latest_score).data
        yield (
            StudentItemSerializer(student_item).data,
            SubmissionSerializer(submission).data,
            serialized_score
        )


def _get_utf8_encoded_rows(rows):
    for row in rows:
        yield [unicode(item).encode('utf-8') for item in row]


def _use_read_replica(queryset):
    return (
        queryset.using("read_replica")
        if "read_replica" in settings.DATABASES
        else queryset
    )
