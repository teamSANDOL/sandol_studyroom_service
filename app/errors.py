"""API가 응답 코드로 바꿔 내보내는 서비스 오류다."""


class ServiceError(Exception):
    """HTTP 상태와 기계 판독 코드를 가진 오류다."""

    status_code = 500
    code = "internal_error"
    message = "요청을 처리하지 못했다."


class SchoolUnavailableError(ServiceError):
    status_code = 502
    code = "school_unavailable"
    message = "학교 좌석 시스템에 연결하지 못했다."


class SchoolResponseError(ServiceError):
    status_code = 502
    code = "school_response_invalid"
    message = "학교 좌석 시스템의 응답 형식이 예상과 다르다."


class ReadingroomNotFoundError(ServiceError):
    status_code = 404
    code = "readingroom_not_found"
    message = "지원하지 않는 열람실 코드다. A1, A2, E1 중 하나를 사용한다."


class SeatNotFoundError(ServiceError):
    status_code = 404
    code = "seat_not_found"
    message = "해당 열람실에 없는 좌석 번호다."
