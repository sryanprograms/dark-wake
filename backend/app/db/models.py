"""SQLAlchemy models for vessel, AIS, SAR timeline, and fusion."""

from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, Boolean, DateTime, Float, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Vessel(Base):
    __tablename__ = "vessel"

    mmsi: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    imo: Mapped[int | None] = mapped_column(BigInteger)
    name: Mapped[str | None] = mapped_column(Text)
    callsign: Mapped[str | None] = mapped_column(Text)
    ship_type: Mapped[str | None] = mapped_column(Text)
    length_m: Mapped[float | None] = mapped_column(Float)
    width_m: Mapped[float | None] = mapped_column(Float)
    flag: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AisPosition(Base):
    __tablename__ = "ais_position"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    mmsi: Mapped[int] = mapped_column(BigInteger, ForeignKey("vessel.mmsi"), nullable=False)
    t: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    sog: Mapped[float | None] = mapped_column(Float)
    cog: Mapped[float | None] = mapped_column(Float)
    heading: Mapped[float | None] = mapped_column(Float)
    nav_status: Mapped[str | None] = mapped_column(Text)


class OperatorEvent(Base):
    __tablename__ = "operator_event"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(Text, nullable=False)
    mmsi: Mapped[int | None] = mapped_column(BigInteger)
    t: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONB)
    geom = mapped_column(Geometry("POINT", srid=4326))
    track_excerpt: Mapped[list | None] = mapped_column(JSONB)
    created_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SarScene(Base):
    __tablename__ = "sar_scene"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    scene_id: Mapped[str] = mapped_column(Text, nullable=False)
    t: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, unique=True)
    detection_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SarDetection(Base):
    __tablename__ = "sar_detection"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(Text, nullable=False)
    scene_id: Mapped[str] = mapped_column(Text, nullable=False)
    t: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    geom = mapped_column(Geometry("POINT", srid=4326), nullable=False)
    length_m: Mapped[float | None] = mapped_column(Float)
    confidence: Mapped[float | None] = mapped_column(Float)
    raw: Mapped[dict | None] = mapped_column(JSONB)


class Contact(Base):
    __tablename__ = "contact"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    sar_detection_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey("sar_detection.id")
    )
    scene_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("sar_scene.id"))
    classification: Mapped[str] = mapped_column(Text, nullable=False)
    matched_mmsi: Mapped[int | None] = mapped_column(BigInteger)
    match_distance_m: Mapped[float | None] = mapped_column(Float)
    match_dt_s: Mapped[float | None] = mapped_column(Float)
    predicted_from_gap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    suspicion: Mapped[float | None] = mapped_column(Float)
    reason: Mapped[str | None] = mapped_column(Text)
    details: Mapped[dict | None] = mapped_column(JSONB)
    t: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    geom = mapped_column(Geometry("POINT", srid=4326))
