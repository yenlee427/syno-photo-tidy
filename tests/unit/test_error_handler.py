from syno_photo_tidy.models import ErrorLevel, ProcessError
from syno_photo_tidy.utils.error_handler import ErrorHandler


def test_error_handler_levels() -> None:
    handler = ErrorHandler()
    handler.add(ProcessError(code="I-001", level=ErrorLevel.INFO, message="ok"))
    handler.add_warning(code="W-001", message="warn")
    handler.add_fatal(code="E-001", message="fail")

    assert len(handler.get_by_level(ErrorLevel.INFO)) == 1
    assert len(handler.get_by_level(ErrorLevel.RECOVERABLE)) == 1
    assert len(handler.get_by_level(ErrorLevel.FATAL)) == 1
