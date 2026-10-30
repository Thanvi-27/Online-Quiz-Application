"""
Custom exceptions shared by every layer.

Explain in viva: one base class (QuizAppError) so the GUI can catch any application
error in a single `except QuizAppError`, while each subclass says what went wrong.
"""


class QuizAppError(Exception):
    """Base class for all application errors."""


class DatabaseError(QuizAppError):
    pass


class AuthenticationError(QuizAppError):
    pass


class AuthorizationError(QuizAppError):
    pass


class ValidationError(QuizAppError):
    pass
