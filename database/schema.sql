CREATE TABLE users (
    id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    running_cp INTEGER,
    running_tte INTEGER,
    running_w_prime INTEGER
);

-- Insert test user
INSERT INTO users (id, first_name, last_name) VALUES ('i95355', 'Test', 'User');

CREATE TABLE gear (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    name TEXT,
    distance FLOAT,
    time FLOAT,
    type TEXT,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE TABLE activities (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL,
    start_date TIMESTAMP NOT NULL,
    fit_file BYTEA NOT NULL,
    name TEXT,
    description TEXT,
    sport_type TEXT,
    duration FLOAT,
    total_elevation_gain FLOAT,
    distance FLOAT,
    average_speed FLOAT,
    average_heartrate INTEGER,
    average_cadence FLOAT,
    average_power FLOAT,
    calories INTEGER,
    average_lr_balance FLOAT,
    gear_id TEXT,
    average_gap FLOAT,
    perceived_exertion INTEGER,
    polarization_index FLOAT,
    decoupling FLOAT,
    carbs_ingested FLOAT,
    normalized_power INTEGER,
    training_load INTEGER,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (gear_id) REFERENCES gear(id)
);

CREATE TABLE activity_laps (
    activity_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    start_date TIMESTAMPTZ NOT NULL,
    duration FLOAT,
    distance FLOAT,
    average_speed FLOAT,
    average_heartrate INTEGER,
    average_cadence FLOAT,
    average_power FLOAT,
    average_lr_balance FLOAT,
    intensity TEXT,
    PRIMARY KEY (activity_id, sequence),
    FOREIGN KEY (activity_id) REFERENCES activities(id)
);

CREATE TABLE activity_streams (
    time TIMESTAMPTZ NOT NULL,
    activity_id TEXT NOT NULL,
    sequence INTEGER NOT NULL,
    latitude FLOAT,
    longitude FLOAT,
    power INTEGER,
    heart_rate INTEGER,
    cadence INTEGER,  -- include fractional cadence
    distance FLOAT,
    altitude FLOAT,
    speed FLOAT,
    temperature FLOAT,
    humidity FLOAT,
    vertical_oscillation FLOAT,
    ground_contact_time FLOAT,
    left_right_balance FLOAT,
    form_power INTEGER,
    leg_spring_stiffness FLOAT,
    air_power INTEGER,
    dfa_a1 FLOAT,
    artifacts FLOAT,
    respiration_rate FLOAT,
    front_gear INTEGER,
    rear_gear INTEGER,
    PRIMARY KEY (time, activity_id, sequence),
    FOREIGN KEY (activity_id) REFERENCES activities(id)
);

CREATE TABLE races (
    id UUID PRIMARY KEY,
    user_id TEXT NOT NULL,
    start_date TIMESTAMP NOT NULL,
    name TEXT,
    distance INTEGER NOT NULL,
    elevation_gain INTEGER,
    gear_id TEXT,
    predicted_duration INTEGER,
    predicted_power INTEGER,
    predicted_running_effectiveness FLOAT,
    predicted_riegel_exponent FLOAT,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (gear_id) REFERENCES gear(id)
);

CREATE TABLE power_curves (
    user_id TEXT NOT NULL,
    sport TEXT NOT NULL,
    duration INTEGER NOT NULL,
    power INTEGER NOT NULL,
    PRIMARY KEY (user_id, sport, duration),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

CREATE EXTENSION IF NOT EXISTS timescaledb;
SELECT create_hypertable('activity_streams', 'time');