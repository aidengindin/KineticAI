import pandas as pd
import numpy as np
import json
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, LSTM, Dense, Concatenate, BatchNormalization, Attention, Softmax, Multiply, Lambda
from tensorflow.keras.regularizers import l2
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.optimizers import Adam
from sklearn.preprocessing import StandardScaler
import joblib
import tensorflow as tf

class DataGenerator(tf.keras.utils.Sequence):
    def __init__(self, df, feature_cols, batch_size=32, seq_length=60, **kwargs):
        super().__init__(**kwargs)
        
        # Preprocess everything once during initialization
        print("Preprocessing data...")
        self.batch_size = batch_size
        self.seq_length = seq_length
        self.feature_cols = feature_cols
        
        # Convert to numpy arrays for faster access
        self.activities = []
        self.targets = []
        
        # Group by activity_id once
        grouped = df.groupby('activity_id')
        
        for activity_id, activity_df in grouped:
            # Sort by timestamp once
            activity_df = activity_df.sort_values('timestamp')

            # Pre-interpolate sequences for this activity
            duration = (activity_df['timestamp'].max() - 
                        activity_df['timestamp'].min()).total_seconds()
            
            if duration < seq_length + 1:
                continue
                    
            # Convert timestamps to seconds once
            times = (activity_df['timestamp'] - 
                    activity_df['timestamp'].iloc[0]).dt.total_seconds().values
            
            # Create sequence start points
            start_indices = range(0, len(activity_df) - seq_length)
            
            for start_idx in start_indices:
                if start_idx + seq_length >= len(activity_df):
                    break
                            
                sequence = np.zeros((seq_length, len(self.feature_cols)))
                
                # Interpolate each feature
                for j, col in enumerate(self.feature_cols):
                    sequence[:, j] = np.interp(
                        np.arange(seq_length),
                        times[start_idx:start_idx + seq_length + 1],
                        activity_df[col].values[start_idx:start_idx + seq_length + 1]
                    )

                target = activity_df['heart_rate_normalized'].values[start_idx + seq_length]
                
                self.activities.append(sequence)
                self.targets.append(target)
        
        self.activities = np.array(self.activities)
        self.targets = np.array(self.targets)
        self.indices = np.arange(len(self.activities))
        print(f"Preprocessed {len(self.activities)} sequences")
            
    def on_epoch_end(self):
        # Shuffle indices at the end of each epoch
        np.random.shuffle(self.indices)
    
    def __len__(self):
        return len(self.activities) // self.batch_size
    
    def __getitem__(self, idx):
        batch_indices = self.indices[idx * self.batch_size:(idx + 1) * self.batch_size]
        return self.activities[batch_indices], self.targets[batch_indices]

class WarmupCallback(tf.keras.callbacks.Callback):
    def __init__(self, max_lr=0.004, min_lr=1e-6, warmup_epochs=10):
        super().__init__()
        self.max_lr = max_lr
        self.min_lr = min_lr
        self.warmup_epochs = warmup_epochs
        self.current_lr = None
    
    def on_train_begin(self, logs=None):
        self.current_lr = self.model.optimizer.learning_rate
        
    def on_epoch_begin(self, epoch, logs=None):
        if epoch < self.warmup_epochs:
            self.current_lr = self.min_lr + (self.max_lr - self.min_lr) * (epoch / self.warmup_epochs)
            tf.keras.backend.set_value(self.model.optimizer.learning_rate, self.current_lr)
        else:
            tf.keras.backend.set_value(self.model.optimizer.learning_rate, self.max_lr)

class WarmupSchedule(tf.keras.optimizers.schedules.LearningRateSchedule):
    def __init__(self, max_lr=0.004, min_lr=1e-6, warmup_epochs=10, steps_per_epoch=None):
        super().__init__()
        self.max_lr = tf.constant(max_lr, dtype=tf.float32)
        self.min_lr = tf.constant(min_lr, dtype=tf.float32)
        self.warmup_steps = tf.constant(warmup_epochs * steps_per_epoch, dtype=tf.float32)
        
    def __call__(self, step):
        step = tf.cast(step, tf.float32)
        return tf.cond(
            step < self.warmup_steps,
            lambda: self.min_lr + (self.max_lr - self.min_lr) * (step / self.warmup_steps),
            lambda: self.max_lr
        )

def generate_data(df, feature_cols, test_fraction=0.2, batch_size=4096, seq_length=120):
    # Shuffle activity IDs
    shuffled_ids = np.random.permutation(df['activity_id'].unique())

    # Split into train/val
    train_ids = shuffled_ids[:int(len(shuffled_ids)*(1-test_fraction))]
    val_ids = shuffled_ids[int(len(shuffled_ids)*(1-test_fraction)):]
    train_df = df[df['activity_id'].isin(train_ids)]
    val_df = df[df['activity_id'].isin(val_ids)]

    # Create generators
    train_gen = DataGenerator(train_df, feature_cols, batch_size=batch_size, seq_length=seq_length)
    val_gen = DataGenerator(val_df, feature_cols, batch_size=batch_size, seq_length=seq_length)

    return train_gen, val_gen

def build_model(feature_cols,
                seq_length=60,
                l2_reg=0.05,
                lr=0.008,
                lstm_units=64,
                steps_per_epoch=10,
                ):

    warmup_schedule = WarmupSchedule(max_lr=lr, min_lr=1e-6, warmup_epochs=10, steps_per_epoch=steps_per_epoch)

    # Build model
    inputs = Input(shape=(seq_length, len(feature_cols)))
    x = LSTM(lstm_units, return_sequences=True,
            kernel_regularizer=l2(l2_reg),
            recurrent_regularizer=l2(l2_reg))(inputs)
    x = BatchNormalization()(x)

    x = Attention()([x, x])

    x = LSTM(lstm_units, return_sequences=True,
            kernel_regularizer=l2(l2_reg),
            recurrent_regularizer=l2(l2_reg))(x)
    x = BatchNormalization()(x)

    x = LSTM(lstm_units // 2, return_sequences=False, kernel_regularizer=l2(l2_reg))(x)
    x = BatchNormalization()(x)

    x = Dense(lstm_units // 2, activation='relu')(x)
    outputs = Dense(1)(x)  # Predict next heart rate

    model = Model(inputs=inputs, outputs=outputs)
    optimizer = Adam(learning_rate=warmup_schedule, clipnorm=1.0)
    model.compile(optimizer=optimizer, loss='mse')

    return model
    
def train_model(model, train_gen, val_gen, lr=0.008, epochs=1000):
    early_stopping = EarlyStopping(
        monitor='val_loss',
        patience=20,
        restore_best_weights=True
    )
    
    lr_scheduler = ReduceLROnPlateau(
        monitor='val_loss',
        factor=0.5,
        patience=5,
        min_lr=1e-6
    )

    with tf.device('/GPU:0'):
        history = model.fit(
            train_gen,
            validation_data=val_gen,
            epochs=epochs,
            # callbacks=[early_stopping, lr_scheduler],
            callbacks=[early_stopping]
        )
    return history

def optimize_hyperparameters(df, feature_cols):
    print('Phase 1: Learning rate & batch size')
    results = []
    for batch_size in [2048, 4096, 8192, 16384]:
        train_gen, val_gen = generate_data(df, feature_cols, batch_size=batch_size)
        steps_per_epoch = len(train_gen)
        for lr in [0.001, 0.002, 0.004, 0.008]:
            model = build_model(feature_cols, lr=np.sqrt(batch_size / 2048) * lr, steps_per_epoch=steps_per_epoch)
            history = train_model(model, train_gen, val_gen, lr=lr, epochs=20)
            mse = history.history['val_loss'][-1]
            results.append({'batch_size': batch_size, 'lr': lr, 'mse': mse})
            print(f"Batch size: {batch_size}, Learning rate: {lr}, MSE: {mse:.4f}")

    results_df = pd.DataFrame(results)
    best = results_df.sort_values('mse').head(1)
    print(f"Best: Batch size: {best['batch_size'].values[0]}, Learning rate: {best['lr'].values[0]}, MSE: {best['mse'].values[0]:.4f}")
    best_batch_size = best['batch_size'].values[0]
    best_lr = best['lr'].values[0] * np.sqrt(best_batch_size / 2048)
    train_gen, val_gen = generate_data(df, feature_cols, batch_size=best_batch_size)
    steps_per_epoch = len(train_gen)

    print('Phase 2: LSTM units')
    results = []
    for lstm_units in [32, 64, 128, 256]:
        model = build_model(feature_cols, lr=best_lr, lstm_units=lstm_units, steps_per_epoch=steps_per_epoch)
        history = train_model(model, train_gen, val_gen, lr=best_lr, epochs=15)
        mse = history.history['val_loss'][-1]
        results.append({'lstm_units': lstm_units, 'mse': mse})
        print(f"LSTM units: {lstm_units}, MSE: {mse:.4f}")

    results_df = pd.DataFrame(results)
    best = results_df.sort_values('mse').head(1)
    print(f"Best: LSTM units: {best['lstm_units'].values[0]}, MSE: {best['mse'].values[0]:.4f}")
    best_lstm_units = best['lstm_units'].values[0]

    print('Phase 3: Regularization')
    results = []
    for l2_reg in [0.01, 0.02, 0.04, 0.08]:
        model = build_model(feature_cols, lr=best_lr, lstm_units=best_lstm_units, l2_reg=l2_reg, steps_per_epoch=steps_per_epoch)
        history = train_model(model, train_gen, val_gen, lr=best_lr, epochs=15)
        mse = history.history['val_loss'][-1]
        results.append({'l2_reg': l2_reg, 'mse': mse})
        print(f"L2 regularization: {l2_reg}, MSE: {mse:.4f}")

    results_df = pd.DataFrame(results)
    best = results_df.sort_values('mse').head(1)
    print(f"Best: L2 regularization: {best['l2_reg'].values[0]}, MSE: {best['mse'].values[0]:.4f}")
    best_l2_reg = best['l2_reg'].values[0]

    print('Phase 4: Sequence length')
    results = []
    for seq_length in [60, 120, 240, 480]:
        model = build_model(feature_cols, lr=best_lr, lstm_units=best_lstm_units, l2_reg=best_l2_reg, steps_per_epoch=steps_per_epoch, seq_length=seq_length)
        history = train_model(model, train_gen, val_gen, lr=best_lr, epochs=10)
        mse = history.history['val_loss'][-1]
        results.append({'seq_length': seq_length, 'mse': mse})
        print(f"Sequence length: {seq_length}, MSE: {mse:.4f}")

    results_df = pd.DataFrame(results)
    best = results_df.sort_values('mse').head(1)
    print(f"Best: Sequence length: {best['seq_length'].values[0]}, MSE: {best['mse'].values[0]:.4f}")
    best_seq_length = best['seq_length'].values[0]

    return best_batch_size, best_lr, best_lstm_units, best_l2_reg, best_seq_length

def collect_prediction_errors(model, val_gen, hr_scaler, feature_scaler, feature_cols):
    """
    Calculate real-world heart rate prediction error on validation data.

    Args:
    model: Trained keras model
    val_gen: DataGenerator instance for validation data
    hr_scaler: StandardScaler fitted on original heart rate values
    feature_scaler: StandardScaler fitted on original feature values
    feature_cols: List of feature columns used in the model

    Returns:
    error_records: List of dictionaries with true heart rate, predicted heart rate, error, and all features
    """

    error_records = []
    
    for i in range(len(val_gen)):
        x_batch, y_batch = val_gen[i]
        predictions = model.predict(x_batch)
        
        # Convert to actual heart rates
        pred_hr = hr_scaler.inverse_transform(predictions)
        true_hr = hr_scaler.inverse_transform(y_batch)
        errors = pred_hr - true_hr
        
        # Process each prediction in batch
        for j in range(len(x_batch)):
            sequence = x_batch[j]
            current = sequence[-1]
            
            # Convert all features to original scale at once
            orig_features = feature_scaler.inverse_transform(
                current.reshape(1, -1)
            )[0]
            
            # Build record
            record = {
                'true_hr': true_hr[j][0],
                'predicted_hr': pred_hr[j][0],
                'error': errors[j][0],
                'sport': 'running' if current[-1] == 1 else 'cycling'
            }
            
            # Add all features
            for k, col in enumerate(feature_cols):
                record[col] = orig_features[k]
                
            error_records.append(record)
    
    return pd.DataFrame(error_records)

def analyze_prediction_errors(errors_df):
    analysis = {
        'basic_stats': errors_df['error'].describe(),
        'by_sport': errors_df.groupby('sport')['error'].describe(),
        'by_intensity': errors_df.groupby(
            pd.qcut(errors_df['speed'], q=10)
        )['error'].describe(),
        'by_temperature': errors_df.groupby(
            pd.qcut(errors_df['temperature_2m'], q=5)
        )['error'].describe(),
        'feature_correlations': errors_df.corr()['error'].sort_values(ascending=False)
    }

    return analysis

if __name__ == "__main__":
    print("GPU Available: ", tf.config.list_physical_devices('GPU'))

    tf.keras.utils.set_random_seed(42)

    df = pd.read_csv('records_df.csv')
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['sport'] = df['sport'].map({'running': 1, 'cycling': 0})

    # Scale features
    feature_cols = ['speed', 'cadence', 'power', 'distance',
                    'temperature_2m',
                    'relative_humidity_2m',
                    'wind_speed_10m',
                    'precipitation', 'cloud_cover',
                    'sport', 'power_ind', 'grade_adjusted_speed',
                    'time_into_activity',
                    'speed_30s', 'grade_adjusted_speed_30s', 'power_30s',
                    'speed_1m', 'grade_adjusted_speed_1m', 'power_1m',
                    'speed_5m', 'grade_adjusted_speed_5m', 'power_5m',
                    'ctl', 'atl', 'tsb', 'kj', 'heat_acclimation',
                    'heat_index', 'wind_chill', 'sun_angle',
                    ]
    scaler = StandardScaler()
    df[feature_cols] = scaler.fit_transform(df[feature_cols].fillna(0))

    # Create separate scaler for heart rate
    hr_scaler = StandardScaler()
    df['heart_rate_normalized'] = hr_scaler.fit_transform(df[['heart_rate']])

    best_batch_size, best_lr, best_lstm_units, best_l2_reg, best_seq_length = optimize_hyperparameters(df, feature_cols)

    train_gen, val_gen = generate_data(df, feature_cols, batch_size=best_batch_size, seq_length=best_seq_length)
    model = build_model(feature_cols, seq_length=best_seq_length, lr=best_lr, lstm_units=best_lstm_units, l2_reg=best_l2_reg)
    history = train_model(model, train_gen, val_gen)

    # Use the function after training
    errors_df = collect_prediction_errors(model, val_gen, hr_scaler, scaler, feature_cols)
    analysis = analyze_prediction_errors(errors_df)

    # Save the model
    model.save('weather-impact-model.keras')

    # Save the scalers
    joblib.dump(scaler, 'scaler.joblib')
    joblib.dump(hr_scaler, 'hr_scaler.joblib')

    # Save the analysis
    with open('analysis.json', 'w') as f:
        json.dump(analysis, f, indent=4)

    print("Model and scalers saved successfully.")
