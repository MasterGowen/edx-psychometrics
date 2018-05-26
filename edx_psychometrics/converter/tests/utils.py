class FakeCourse:
    def __init__(self, *, modules={}, content=None):
        self.content = content or {}
        self.modules = modules or {}


class FakeAnswers:
    def __init__(self, answers=None):
        self.answers = answers or ()
