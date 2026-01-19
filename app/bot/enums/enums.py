from enum import Enum

class UserRole(str, Enum):
    OWNER = 'owner'
    ADMIN = 'admin'
    STUDENT = 'student'
    GUEST = 'guest'

class FileType(str, Enum):
    LECTURE = 'lecture',
    LAB = 'lab',
    SUBMISSION = 'submission'

class SubmissionStatus(str, Enum):
    UPLOADED = 'uploaded',
    GRADED = 'graded'