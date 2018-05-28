from submissions.serializers import (
    SubmissionSerializer, StudentItemSerializer, ScoreSerializer, UnannotatedScoreSerializer
)
from submissions.models import Submission, StudentItem, Score, ScoreSummary, ScoreAnnotation, score_set, score_reset
from django.conf import settings

def get_course_item_submissions(course_id, item_id, item_type, read_replica=True):
    """ For the given course, get all student items of the given item type, all the submissions for those itemes,
    and the latest scores for each item. If a submission was given a score that is not the latest score for the
    relevant student item, it will still be included but without score.
    Args:
        course_id (str): The course that we are getting submissions from.
        item_type (str): The type of items that we are getting submissions for.
        read_replica (bool): Try to use the database's read replica if it's available.
    Yields:
        A tuple of three dictionaries representing:
        (1) a student item with the following fields:
            student_id
            course_id
            student_item
            item_type
        (2) a submission with the following fields:
            student_item
            attempt_number
            submitted_at
            created_at
            answer
        (3) a score with the following fields, if one exists and it is the latest score:
            (if both conditions are not met, an empty dict is returned here)
            student_item
            submission
            points_earned
            points_possible
            created_at
            submission_uuid
    """
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

            # Only include the score if it is not a reset score (is_hidden), and if the current submission is the same
            # as the student_item's latest score's submission. This matches the behavior of the API's get_score method.
            if (not latest_score.is_hidden()) and latest_score.submission.uuid == submission.uuid:
                serialized_score = ScoreSerializer(latest_score).data
        yield (
            StudentItemSerializer(student_item).data,
            SubmissionSerializer(submission).data,
            serialized_score
        )

def _use_read_replica(queryset):
    """
    Use the read replica if it's available.
    Args:
        queryset (QuerySet)
    Returns:
        QuerySet
    """
    return (
        queryset.using("read_replica")
        if "read_replica" in settings.DATABASES
        else queryset
    )