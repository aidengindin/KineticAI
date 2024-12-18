CREATE TABLE activity (
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
    FOREIGN KEY (user_id) REFERENCES user(id),
    FOREIGN KEY (gear_id) REFERENCES gear(id)
);

CREATE TABLE user (
    id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT
);

CREATE TABLE gear (
    id TEXT PRIMARY KEY,
    name TEXT,
    distance FLOAT
);

CREATE TABLE activity_lap (
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
    FOREIGN KEY (activity_id) REFERENCES activity(id)
);

CREATE TABLE activity_stream (
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
    vertical_osciillation FLOAT,
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
    FOREIGN KEY (activity_id) REFERENCES activity(id)
);
SELECT create_hypertable('activity_stream', 'time');
