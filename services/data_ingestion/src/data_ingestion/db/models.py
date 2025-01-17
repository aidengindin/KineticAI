from datetime import datetime
from typing import Optional
from sqlalchemy import Column, String, DateTime, Float, Integer, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship

from data_ingestion.db.database import Base

class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    first_name = Column(String)
    last_name = Column(String)

class Gear(Base):
    __tablename__ = "gear"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    name = Column(String, nullable=False)
    description = Column(String)
    brand = Column(String)
    model = Column(String)
    type = Column(String)
    distance = Column(Float)
    time = Column(Float)

    user = relationship("User", backref="gear")

class Activity(Base):
    __tablename__ = "activities"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False)
    start_date = Column(DateTime, nullable=False)
    name = Column(String)
    description = Column(String)
    sport_type = Column(String)
    duration = Column(Float)
    total_elevation_gain = Column(Float)
    distance = Column(Float)
    average_speed = Column(Float)
    average_heartrate = Column(Integer)
    average_cadence = Column(Float)
    average_power = Column(Float)
    calories = Column(Integer)
    average_lr_balance = Column(Float)
    gear_id = Column(String, ForeignKey("gear.id"), nullable=True)
    average_gap = Column(Float)
    perceived_exertion = Column(Integer)
    polarization_index = Column(Float)
    decoupling = Column(Float)
    carbs_ingested = Column(Float)
    normalized_power = Column(Integer)
    training_load = Column(Integer)
    fit_file = Column(LargeBinary, nullable=False)

    user = relationship("User", backref="activities")
    gear = relationship("Gear", backref="activities")
    laps = relationship("ActivityLap", back_populates="activity")
    streams = relationship("ActivityStream", back_populates="activity")

class ActivityLap(Base):
    __tablename__ = "activity_laps"

    activity_id = Column(String, ForeignKey("activities.id"), primary_key=True, nullable=False)
    sequence = Column(Integer, primary_key=True, nullable=False)
    start_date = Column(DateTime(timezone=True), nullable=False)
    duration = Column(Float)
    distance = Column(Float)
    average_speed = Column(Float)
    average_heartrate = Column(Integer)
    average_cadence = Column(Float)
    average_power = Column(Float)
    average_lr_balance = Column(Float)
    intensity = Column(String)

    activity = relationship("Activity", back_populates="laps")

class ActivityStream(Base):
    __tablename__ = "activity_streams"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    activity_id = Column(String, ForeignKey("activities.id"), primary_key=True, nullable=False)
    sequence = Column(Integer, primary_key=True, nullable=False)
    latitude = Column(Float)
    longitude = Column(Float)
    power = Column(Integer)
    heart_rate = Column(Integer)
    cadence = Column(Integer)
    distance = Column(Float)
    altitude = Column(Float)
    speed = Column(Float)
    temperature = Column(Float)
    humidity = Column(Float)
    vertical_oscillation = Column(Float)
    ground_contact_time = Column(Float)
    left_right_balance = Column(Float)
    form_power = Column(Integer)
    leg_spring_stiffness = Column(Float)
    air_power = Column(Integer)
    dfa_a1 = Column(Float)
    artifacts = Column(Float)
    respiration_rate = Column(Float)
    front_gear = Column(Integer)
    rear_gear = Column(Integer)

    activity = relationship("Activity", back_populates="streams") 