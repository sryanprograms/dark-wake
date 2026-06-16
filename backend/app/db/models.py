"""SQLAlchemy models for Phase 1 (vessel + ais_position)."""

from __future__ import annotations

from datetime import datetime

from geoalchemy2 import Geometry
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Text
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
