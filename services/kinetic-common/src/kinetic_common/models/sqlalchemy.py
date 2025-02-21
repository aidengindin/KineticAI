from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, Float, Integer, String, LargeBinary
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass

class User(Base):
    """User model for database storage."""
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    first_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    weight: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    running_cp: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    running_tte: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    running_w_prime: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    running_k: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cycling_cp: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cycling_tte: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cycling_w_prime: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cycling_k: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

class Activity(Base):
    """Activity model for database storage."""
    __tablename__ = "activities"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    name: Mapped[str] = mapped_column(String)
    sport_type: Mapped[str] = mapped_column(String)
    duration: Mapped[float] = mapped_column(Float)
    distance: Mapped[float] = mapped_column(Float)
    average_speed: Mapped[float] = mapped_column(Float)
    average_heartrate: Mapped[float] = mapped_column(Float)
    gear_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    fit_file: Mapped[bytes] = mapped_column(LargeBinary)

class ActivityLap(Base):
    """Activity lap model for database storage."""
    __tablename__ = "activity_laps"

    activity_id: Mapped[str] = mapped_column(String, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration: Mapped[float] = mapped_column(Float)
    distance: Mapped[float] = mapped_column(Float)
    average_speed: Mapped[float] = mapped_column(Float)
    average_heartrate: Mapped[float] = mapped_column(Float)
    average_cadence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    average_power: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    average_lr_balance: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    intensity: Mapped[Optional[str]] = mapped_column(String, nullable=True)

class ActivityStream(Base):
    """Activity stream model for database storage."""
    __tablename__ = "activity_streams"

    activity_id: Mapped[str] = mapped_column(String, primary_key=True)
    sequence: Mapped[int] = mapped_column(Integer, primary_key=True)
    time: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    altitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    heart_rate: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cadence: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    power: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    speed: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    temperature: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    dfa_a1: Mapped[Optional[float]] = mapped_column(Float, nullable=True) 

class Gear(Base):
    """Gear model for database storage."""
    __tablename__ = "gear"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    distance: Mapped[float] = mapped_column(Float)
    time: Mapped[float] = mapped_column(Float)
    type: Mapped[str] = mapped_column(String)

class Race(Base):
    __tablename__ = "races"

    id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[str] = mapped_column(String)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    distance: Mapped[int] = mapped_column(Integer)
    elevation_gain: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    gear_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    predicted_duration: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    predicted_power: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    predicted_running_effectiveness: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    predicted_riegel_exponent: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

class PowerCurve(Base):
    __tablename__ = "power_curves"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    sport: Mapped[str] = mapped_column(String, primary_key=True)
    duration: Mapped[int] = mapped_column(Integer, primary_key=True)
    power: Mapped[int] = mapped_column(Integer)
