import json
import StringIO

from submissions.serializers import (
    SubmissionSerializer, StudentItemSerializer, ScoreSerializer, UnannotatedScoreSerializer
)
from submissions.models import Submission, StudentItem, Score, ScoreSummary, ScoreAnnotation, score_set, score_reset
from django.conf import settings
from eventtracking import tracker
from lms.djangoapps.instructor_task.models import ReportStore

from lms.djangoapps.instructor_task.tasks_helper.utils import tracker_emit

from lms.djangoapps.instructor_task.models import DjangoStorageReportStore

from django.core.files.storage import get_valid_filename
from django.core.files.base import ContentFile
import codecs
import csv

def upload_csv_to_report_store_by_semicolon(rows, csv_name, course_id, timestamp, config_name='GRADES_DOWNLOAD'):
    report_store = ReportStore.from_config(config_name)
    store_rows_by_semicolon(
        report_store,
        course_id,
        u"{course_prefix}_{csv_name}_{timestamp_str}.csv".format(
            course_prefix=get_valid_filename(unicode("_").join([course_id.org, course_id.course, course_id.run])),
            csv_name=csv_name,
            timestamp_str=timestamp.strftime("%Y-%m-%d-%H%M")
        ),
        rows
    )
    tracker_emit(csv_name)

def upload_json_to_report_store(rows, csv_name, course_id, timestamp, config_name='GRADES_DOWNLOAD'):
    report_store = ReportStore.from_config(config_name)
    store_json_file(
        report_store,
        course_id,
        u"{course_prefix}_{csv_name}_{timestamp_str}_test.json".format(
            course_prefix=get_valid_filename(unicode("_").join([course_id.org, course_id.course, course_id.run])),
            csv_name=csv_name,
            timestamp_str=timestamp.strftime("%Y-%m-%d-%H%M")
        ),
        rows
    )
    tracker_emit(csv_name)

def store_json_file(self, course_id, filename, rows):
    file = self.path_to(course_id, filename)
    outfile = StringIO.StringIO()
    outfile.write(json.dumps(rows))
    self.store(course_id, filename, outfile)

    # with open(file, 'w') as outfile:
    #     json.dump(rows, outfile)

def store_rows_by_semicolon(self, course_id, filename, rows):
    output_buffer = ContentFile('')
    output_buffer.write(codecs.BOM_UTF8)
    csvwriter = csv.writer(output_buffer, delimiter=';')
    csvwriter.writerows(DjangoStorageReportStore._get_utf8_encoded_rows(self, rows))
    output_buffer.seek(0)
    self.store(course_id, filename, output_buffer)




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

def _use_read_replica(queryset):
    return (
        queryset.using("read_replica")
        if "read_replica" in settings.DATABASES
        else queryset
    )