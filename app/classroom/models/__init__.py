"""강의실 도메인의 DB 테이블 모델과 Base 를 제공한다."""

from app.classroom.models.base import Base
from app.classroom.models.building import Building
from app.classroom.models.classroom import Classroom
from app.classroom.models.lecture import Lecture, LectureSlot

__all__ = ["Base", "Building", "Classroom", "Lecture", "LectureSlot"]
