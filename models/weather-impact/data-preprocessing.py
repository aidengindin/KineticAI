import os
import numpy as np
from fitparse import FitFile, FitParseError
import pandas as pd
from pathlib import Path
from tqdm import tqdm
import csv
import requests
from datetime import datetime, timedelta
import time
from astral import LocationInfo
from astral.sun import sun, elevation

def preprocess_fit_files(fit_directory: str) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Process all FIT files in directory and return two DataFrames:
    1. A DataFrame with detailed activity records
    2. A DataFrame with activity-level metadata for all activities
    
    Returns:
        tuple: (records_df, metadata_df)
    """
    
    # Get all fit files
    fit_files = [f for f in Path(fit_directory).glob('*.fit')]
    print(f"Found {len(fit_files)} FIT files")
    
    # Initialize counters
    skipped_files = 0
    processed_files = 0
    total_records = 0
    
    # Store all records and metadata
    all_records = []
    all_metadata = []
    
    # Process each file
    for fit_path in tqdm(fit_files):
        new_records_count = 0
        try:
            fit_path_str = str(fit_path)
            fit_file = FitFile(fit_path_str)
            session_msg = next(fit_file.get_messages('session'))
            
            # Extract metadata for all activities
            activity_id = fit_path.stem
            start_time = session_msg.get_value('start_time')
            duration = session_msg.get_value('total_timer_time') or session_msg.get_value('total_elapsed_time')

            if session_msg.get_value('avg_heart_rate'):
                # Try to get avg_heart_rate from session, otherwise calculate from records
                avg_heart_rate = session_msg.get_value('avg_heart_rate')
            else:
                # Calculate average from records that have heart rate
                hr_values = [r.get_value('heart_rate') for r in fit_file.get_messages('record') 
                            if r.get_value('heart_rate')]
                avg_heart_rate = sum(hr_values) / len(hr_values) if hr_values else 0
            trimp = avg_heart_rate * duration / 60
            
            if start_time:
                metadata = {
                    'activity_id': activity_id,
                    'timestamp': start_time,
                    'date': start_time.date(),
                    'total_duration': duration,
                    'total_distance': session_msg.get_value('total_distance'),
                    'avg_heart_rate': avg_heart_rate,
                    'trimp': trimp,
                    'sport': session_msg.get_value('sport'),
                }
                all_metadata.append(metadata)

            # Only process detailed records for outdoor running/cycling
            if session_msg.get_value('sport') not in ['running', 'cycling']:
                continue
            if session_msg.get_value('sub_sport') in ['indoor_running', 'indoor_cycling', 'virtual_activity']:
                continue
            records = list(fit_file.get_messages('record'))
            has_position_data = any(r.get_value('position_lat') is not None for r in records[:60])
            if not has_position_data:
                continue
            
            # If we get here, process the activity records
            sport = session_msg.get_value('sport')
            has_stryd = any('air power' in field.name.lower() for field in session_msg.fields)
            has_power = any('power' in field.name.lower() for field in session_msg.fields)

            power_ind = 0

            if sport == 'running':
                power_ind = 1 if has_stryd else 0
            elif sport == 'cycling':
                power_ind = 1 if has_power else 0
            
            for record in fit_file.get_messages('record'):
                try:
                    power = 0
                    if sport == 'running' and has_stryd:
                            power = record.get_value('power')
                    elif sport == 'cycling' and has_power:
                        power = record.get_value('power')

                    speed = record.get_value('speed') or record.get_value('enhanced_speed')
                    altitude = record.get_value('altitude') or record.get_value('enhanced_altitude') or 0

                    # Extract relevant features
                    record_dict = {
                        'activity_id': activity_id,
                        'timestamp': record.get_value('timestamp'),
                        'date': start_time.date(),
                        'sport': sport,
                        'heart_rate': record.get_value('heart_rate'),
                        'speed': speed,
                        'cadence': record.get_value('cadence'),
                        'power_ind': power_ind,
                        'power': power,
                        'latitude': record.get_value('position_lat'),
                        'longitude': record.get_value('position_long'),
                        'altitude': altitude,
                        'time_into_activity': int((record.get_value('timestamp') - start_time).total_seconds()),
                        'distance': record.get_value('distance')
                    }
                    
                    # Only add records that have at least heart rate and speed
                    if record_dict['heart_rate'] is not None and speed is not None:
                        all_records.append(record_dict)
                        new_records_count += 1
                        
                except Exception as e:
                    print(f"Error processing record in {fit_path}: {str(e)}")
                    continue
            
            total_records += new_records_count
            processed_files += 1
            
        except Exception as e:
            print(f"Error processing file {fit_path}: {str(e)}")
            skipped_files += 1
            continue
    
    print(f"\nProcessing complete:")
    print(f"Processed {processed_files} files")
    print(f"Skipped {skipped_files} files")
    print(f"Total records: {total_records}")
    
    # Convert records to DataFrames
    records_df = pd.DataFrame(all_records)
    records_df['timestamp'] = pd.to_datetime(records_df['timestamp'])
    records_df['date'] = pd.to_datetime(records_df['date'])
    metadata_df = pd.DataFrame(all_metadata)
    metadata_df['timestamp'] = pd.to_datetime(metadata_df['timestamp'])
    metadata_df['date'] = pd.to_datetime(metadata_df['date'])
    
    return records_df, metadata_df

def convert_coordinates(records_df: pd.DataFrame) -> None:
    """Convert coordinates from semicircles to degrees in place."""

    print("Converting coordinates...")
    
    # Conversion constant
    SEMICIRCLES_TO_DEGREES = 180.0 / (2**31)
    
    # Convert coordinates in place
    records_df['latitude'] = records_df['latitude'] * SEMICIRCLES_TO_DEGREES
    records_df['longitude'] = records_df['longitude'] * SEMICIRCLES_TO_DEGREES

def add_weather_data(df: pd.DataFrame) -> None:
    """Add weather data to activity records, modifying the DataFrame in-place."""
    
    print("Preprocessing data for weather data...")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    
    # Filter out (0,0) coordinates
    df.drop(df[((df['latitude'] == 0) & (df['longitude'] == 0))].index, inplace=True)
    df.sort_values(['activity_id', 'timestamp'], inplace=True)
    
    # Create weather timestamp column (rounded to nearest 30 minutes)
    df['weather_timestamp'] = df['timestamp'].dt.floor('30min')
    df['lat_rounded'] = df['latitude'].round(2)
    df['lon_rounded'] = df['longitude'].round(2)
    
    # For each activity, sample location every 30 minutes
    weather_points = df.groupby(['activity_id', 'weather_timestamp']).agg({
        'lat_rounded': 'first',
        'lon_rounded': 'first'
    }).reset_index()
    
    # Get unique location-time combinations
    unique_queries = weather_points.drop_duplicates(['lat_rounded', 'lon_rounded', 'weather_timestamp'])
    print(f"Found {len(unique_queries)} unique location-time combinations")
    
    # Initialize weather data storage
    weather_cache = {}
    
    # Weather variables we want
    hourly_params = [
        'temperature_2m',
        'relative_humidity_2m',
        'dew_point_2m',
        'wind_speed_10m',
        'wind_direction_10m',
        'precipitation',
        'cloud_cover',
        'surface_pressure'
    ]
    
    print("Fetching weather data...")
    # Process in batches to avoid rate limits
    batch_size = 100
    for i in tqdm(range(0, len(unique_queries), batch_size)):
        batch = unique_queries.iloc[i:i+batch_size]
        
        for _, row in batch.iterrows():
            cache_key = (row['lat_rounded'], row['lon_rounded'], row['weather_timestamp'])
            
            if cache_key in weather_cache:
                continue
                
            # Get weather data for this location and hour
            start_date = row['weather_timestamp'].strftime('%Y-%m-%d')
            end_date = (row['weather_timestamp'] + timedelta(days=1)).strftime('%Y-%m-%d')
            
            url = 'https://archive-api.open-meteo.com/v1/archive'
            params = {
                'latitude': row['lat_rounded'],
                'longitude': row['lon_rounded'],
                'start_date': start_date,
                'end_date': end_date,
                'hourly': ','.join(hourly_params)
            }
            
            try:
                response = requests.get(url, params=params)
                response.raise_for_status()
                data = response.json()
                
                # Find the matching hour in the response
                target_hour = row['weather_timestamp']
                target_hour_str = target_hour.strftime('%Y-%m-%dT%H:00')
                
                try:
                    hour_index = data['hourly']['time'].index(target_hour_str)
                    
                    # Store weather data for this location-hour
                    weather_cache[cache_key] = {
                        param: data['hourly'][param][hour_index]
                        for param in hourly_params
                    }
                except ValueError:
                    print(f"Could not find hour {target_hour_str} in weather data")
                    continue
                
                # Respect rate limits
                time.sleep(0.1)
                
            except Exception as e:
                print(f"Error fetching weather data for {row['lat_rounded']}, {row['lon_rounded']}, {row['weather_timestamp']}: {str(e)}")
                continue
    
    print("Adding weather data to records...")
    # Initialize weather columns with None
    for param in hourly_params:
        df[param] = None
    
    # Group by activity to ensure we use the right weather data within each activity
    for activity_id, group in tqdm(df.groupby('activity_id')):
        # Get weather points for this activity
        activity_weather = weather_points[weather_points['activity_id'] == activity_id]
        
        # For each record in the activity
        for idx, record in group.iterrows():
            # Find the closest weather timestamp for this record
            weather_matches = activity_weather[
                (activity_weather['weather_timestamp'] >= record['weather_timestamp'] - pd.Timedelta(minutes=30)) &
                (activity_weather['weather_timestamp'] <= record['weather_timestamp'] + pd.Timedelta(minutes=30))
            ]
            
            if len(weather_matches) > 0:
                # Use the closest weather point in time
                closest_weather = weather_matches.iloc[0]
                cache_key = (
                    closest_weather['lat_rounded'],
                    closest_weather['lon_rounded'],
                    closest_weather['weather_timestamp']
                )
                
                if cache_key in weather_cache:
                    # Update weather data directly in the DataFrame
                    for param, value in weather_cache[cache_key].items():
                        df.at[idx, param] = value
    
    # Clean up temporary columns
    df.drop(['lat_rounded', 'lon_rounded', 'weather_timestamp'], axis=1, inplace=True)
    
    # Print some stats
    print("\nWeather data statistics:")
    for param in hourly_params:
        missing = df[param].isna().sum()
        print(f"{param}: {missing} missing values ({missing/len(df)*100:.1f}%)")

def calculate_grade_adjusted_speed(df: pd.DataFrame, window_size: int = 5) -> None:
    """
    Calculate grade adjusted speed using a rolling window to determine gradient.
    Modifies the input DataFrame in-place.
    
    Args:
        df: DataFrame with latitude, longitude, altitude, and speed columns
        window_size: Number of records to look forward/backward for gradient calculation
    """
    
    def calculate_gradient(group):
        """Calculate gradient for each point using surrounding records"""
        
        # Convert lat/lon to distances
        R = 6371000  # Earth radius in meters
        
        # Convert latitude and longitude to radians
        lat = np.radians(group['latitude'])
        lon = np.radians(group['longitude'])
        
        # Calculate distances between consecutive points
        dlat = lat.diff()
        dlon = dlon = lon.diff()
        
        # Haversine formula for distance
        a = np.sin(dlat/2)**2 + np.cos(lat) * np.cos(lat.shift()) * np.sin(dlon/2)**2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1-a))
        distances = R * c
        
        # Calculate elevation changes
        elevation_changes = group['altitude'].diff()
        
        # Calculate gradients
        gradients = elevation_changes / distances
        
        # Replace inf/nan with 0
        gradients = gradients.fillna(0).replace([np.inf, -np.inf], 0)
        
        # Use rolling average to smooth gradients
        gradients = gradients.rolling(window=window_size, center=True).mean().fillna(0)
        
        return gradients
    
    def calculate_relative_cost(gradient):
        """Calculate relative cost using the formula"""
        i = gradient * 100  # Convert to percentage
        return 15.14 * (i/100)**2 - 2.896 * (i/100)
    
    # Initialize new columns with float type
    df['gradient'] = 0.0
    df['grade_adjusted_speed'] = df['speed'].astype(float)
    
    # Group by activity_id to ensure we don't calculate gradients across activities
    print("Calculating grade adjusted speed...")
    for activity_id, group in tqdm(df.groupby('activity_id')):
        if group['sport'].iloc[0] != 'running':
            continue
            
        # Get indices for this group
        idx = group.index
        
        # Calculate gradients
        gradients = calculate_gradient(group)
        
        # Calculate relative cost
        relative_cost = calculate_relative_cost(gradients)
        
        # Update values in original dataframe
        df.loc[idx, 'gradient'] = gradients.astype(float)
        df.loc[idx, 'grade_adjusted_speed'] = (group['speed'] / (1 + relative_cost)).astype(float)

def calculate_tsb(metadata_df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculate Training Stress Balance (TSB) metrics for each day.
    Each day's TSB values reflect only activities from previous days,
    representing training stress balance at the start of the day.
    
    Args:
        metadata_df: DataFrame containing activity metadata with timestamp and trimp
        
    Returns:
        DataFrame with daily ATL (7-day), CTL (42-day), and TSB values
    """

    print("Calculating TSB...")

    # Ensure date column is datetime
    metadata_df['date'] = pd.to_datetime(metadata_df['date'])
    
    # Create a daily series of TRIMP scores, but shift them to the next day
    # (each activity affects TSB starting the next day)
    daily_trimp = metadata_df.groupby('date')['trimp'].sum().reset_index()
    daily_trimp['date'] = daily_trimp['date'] + pd.Timedelta(days=1)
    
    # Create date range from first activity to day after last activity
    # (to include the effect of the last activity)
    date_range = pd.date_range(
        start=metadata_df['date'].min(),
        end=metadata_df['date'].max() + pd.Timedelta(days=1),
        freq='D'
    )
    
    # Create complete daily DataFrame with zeros for missing days
    complete_daily = pd.DataFrame({'date': date_range})
    
    # Merge and fill missing values
    complete_daily = complete_daily.merge(
        daily_trimp, 
        on='date', 
        how='left'
    ).fillna(0)
    
    # Calculate exponentially weighted averages
    # For ATL: 7 days → alpha = 2/(7+1) = 0.25
    # For CTL: 42 days → alpha = 2/(42+1) = 0.0465
    complete_daily['atl'] = complete_daily['trimp'].ewm(alpha=0.25, adjust=False).mean()
    complete_daily['ctl'] = complete_daily['trimp'].ewm(alpha=0.0465, adjust=False).mean()
    
    # Calculate TSB
    complete_daily['tsb'] = complete_daily['ctl'] - complete_daily['atl']
    
    return complete_daily

def add_tsb(records_df: pd.DataFrame, tsb_df: pd.DataFrame) -> None:
    """Add TSB to records_df in place by matching on date"""

    print("Adding TSB to records...")
    
    # Map TSB values using date
    records_df['ctl'] = records_df['date'].map(tsb_df.set_index('date')['ctl'])
    records_df['atl'] = records_df['date'].map(tsb_df.set_index('date')['atl'])
    records_df['tsb'] = records_df['date'].map(tsb_df.set_index('date')['tsb'])
    
def calculate_kj(records_df: pd.DataFrame) -> None:
    """Calculate cumulative kilojoules for activities with power data."""
    
    print("Calculating kJ...")
    
    # Only calculate for activities with power data
    activities_with_power = records_df[records_df['power_ind'] == 1]['activity_id'].unique()
    
    # Initialize kj column with float type
    records_df['kj'] = 0.0
    
    # For each activity with power data
    for activity_id in tqdm(activities_with_power):
        activity_mask = records_df['activity_id'] == activity_id
        # Calculate cumulative sum of power values converted to kJ (power * seconds / 1000)
        records_df.loc[activity_mask, 'kj'] = (
            records_df.loc[activity_mask, 'power'].cumsum() / 1000
        ).astype(float)

def calculate_heat_index(records_df: pd.DataFrame) -> None:
    """
    Calculate heat index using temperature and relative humidity.
    Modifies the DataFrame in place.
    """
    
    print("Calculating heat index...")
    
    # Coefficients for Celsius formula
    c1 = -8.784694755
    c2 = 1.61139411
    c3 = 2.338548838
    c4 = -0.14611605
    c5 = -0.012308094
    c6 = -0.016424827778
    c7 = 2.211732e-3
    c8 = 7.2546e-4
    c9 = -3.582e-6
    
    # Get temperature and relative humidity
    T = records_df['temperature_2m']
    R = records_df['relative_humidity_2m']
    
    # Calculate heat index using the formula
    HI = (c1 + 
          c2 * T + 
          c3 * R + 
          c4 * T * R + 
          c5 * T**2 + 
          c6 * R**2 + 
          c7 * T**2 * R + 
          c8 * T * R**2 + 
          c9 * T**2 * R**2)
    
    # Add to DataFrame
    records_df['heat_index'] = HI

def add_rolling_averages(records_df: pd.DataFrame) -> None:
    """
    Calculate rolling averages for speed, grade adjusted speed, and power.
    Adds columns for 30s, 1m, and 5m averages in place.
    Each average represents the mean of the previous window, with the current record
    being the last value in that window.
    """
    # Define windows in seconds
    windows = {
        '30s': 30,
        '1m': 60,
        '5m': 300
    }
    
    # Columns to calculate averages for
    metrics = ['speed', 'grade_adjusted_speed', 'power']
    
    # Process each activity separately
    print("Calculating rolling averages...")
    for activity_id in tqdm(records_df['activity_id'].unique()):
        activity_mask = records_df['activity_id'] == activity_id
        activity_df = records_df[activity_mask].copy()
        
        # Calculate rolling averages for each window and metric
        for window_name, window_size in windows.items():
            for metric in metrics:
                if metric in activity_df.columns:  # Only process if column exists
                    col_name = f'{metric}_{window_name}'
                    activity_df[col_name] = activity_df[metric].rolling(
                        window=window_size,
                        min_periods=1,
                        center=False  # Window ends at current record
                    ).mean()
                    
                    # Update the main dataframe
                    records_df.loc[activity_mask, col_name] = activity_df[col_name]

def calculate_wind_chill(records_df: pd.DataFrame) -> None:
    """
    Calculate wind chill using Environment Canada formula.
    Formula: Twc = 13.12 + 0.6215Ta - 11.37v^0.16 + 0.3965Ta*v^0.16
    where:
    - Twc is wind chill index in Celsius
    - Ta is air temperature in Celsius
    - v is wind speed in km/h
    
    Modifies the DataFrame in place.
    """
    
    print("Calculating wind chill...")
    
    # Get temperature and wind speed
    Ta = records_df['temperature_2m']
    v = records_df['wind_speed_10m'] * 3.6  # Convert m/s to km/h
    
    # Calculate wind chill only when temperature is below 10°C
    mask = Ta < 10
    
    # Initialize wind chill column with temperature (no wind chill effect above 10°C)
    records_df['wind_chill'] = Ta
    
    # Calculate wind chill where applicable
    v_powered = v[mask] ** 0.16
    records_df.loc[mask, 'wind_chill'] = (
        13.12 + 
        0.6215 * Ta[mask] - 
        11.37 * v_powered + 
        0.3965 * Ta[mask] * v_powered
    )

def calculate_sun_angle(records_df: pd.DataFrame) -> None:
    """
    Calculate sun angle (solar elevation) for each record using timestamp and location.
    Uses the astral library for astronomical calculations.
    Adds sun_angle column to the DataFrame in place.
    """
    
    print("Calculating sun angle...")
    
    # Initialize sun angle column
    records_df['sun_angle'] = None
    
    # Process in chunks to avoid memory issues
    chunk_size = 10000
    for start_idx in tqdm(range(0, len(records_df), chunk_size)):
        chunk = records_df.iloc[start_idx:start_idx + chunk_size]
        
        # Calculate sun angle for each record in chunk
        for idx, record in chunk.iterrows():
            try:
                # Create location object
                loc = LocationInfo(
                    latitude=record['latitude'],
                    longitude=record['longitude']
                )
                
                # Calculate sun elevation at this timestamp and location
                sun_elevation = elevation(
                    loc.observer,
                    record['timestamp'].replace(tzinfo=None)  # astral expects naive datetime
                )
                
                # Update the main DataFrame
                records_df.at[idx, 'sun_angle'] = sun_elevation
                
            except Exception as e:
                print(f"Error calculating sun angle for record {idx}: {str(e)}")
                continue

def add_weather_metadata(records_df: pd.DataFrame, metadata_df: pd.DataFrame) -> None:
    """
    Calculate average weather metrics for each activity and add them to metadata_df.
    Adds temperature_2m, relative_humidity_2m, and heat_index columns to metadata_df.
    
    Args:
        records_df: DataFrame containing detailed activity records with weather data
        metadata_df: DataFrame containing activity metadata to be updated
    """
    
    print("Calculating mean weather metrics...")
    
    # Calculate mean weather metrics for each activity
    weather_means = records_df.groupby('activity_id').agg({
        'temperature_2m': 'mean',
        'relative_humidity_2m': 'mean',
        'heat_index': 'mean'
    }).round(2)
    
    # Add weather metrics to metadata_df
    metadata_df['temperature_2m'] = metadata_df['activity_id'].map(weather_means['temperature_2m'])
    metadata_df['relative_humidity_2m'] = metadata_df['activity_id'].map(weather_means['relative_humidity_2m'])
    metadata_df['heat_index'] = metadata_df['activity_id'].map(weather_means['heat_index'])

def add_heat_acclimation(records_df: pd.DataFrame, metadata_df: pd.DataFrame, tsb_df: pd.DataFrame, temperature_threshold: float = 20.0, alpha: float = 0.2) -> None:
    """
    Calculate heat load per activity in metadata_df and daily heat acclimation in tsb_df and records_df.
    Heat acclimation is an exponentially weighted moving average of prior days' heat loads.
    Each day's heat acclimation represents acclimation upon waking (excludes same-day activities).
    
    Args:
        records_df: DataFrame with columns 'timestamp' and 'heat_index'
        metadata_df: DataFrame with activity metadata
        tsb_df: DataFrame with daily training metrics
        temperature_threshold: float, temperature in Celsius above which to count exposure
        alpha: float, smoothing factor for exponential moving average
    """
    # Ensure timestamps are datetime
    metadata_df.sort_values('date', inplace=True)
    
    # Calculate per-activity heat load
    metadata_df['heat_load'] = (
        (metadata_df['heat_index'] - temperature_threshold).clip(lower=0) *
        (metadata_df['total_duration'] / 3600.0)  # Convert seconds to hours
    )
    
    # Calculate daily heat acclimation (using only prior days)
    heat_accl_values = []
    ewma_value = 0.0
    
    print("Calculating heat acclimation...")
    for date in tqdm(tsb_df['date']):
        # Add current ewma to results before updating with prior day's activities
        heat_accl_values.append(ewma_value)
        
        # Get prior day's activities
        prior_day = date - pd.Timedelta(days=1)
        prior_activities = metadata_df[metadata_df['date'] == prior_day]
        
        # Update ewma with total heat load from prior day
        if len(prior_activities) > 0:
            prior_heat_load = prior_activities['heat_load'].sum()
            ewma_value = alpha * prior_heat_load + (1 - alpha) * ewma_value
    
    # Add heat acclimation to tsb_df
    tsb_df['heat_acclimation'] = heat_accl_values
    
    # Add heat acclimation to records_df
    records_df['heat_acclimation'] = records_df['date'].map(pd.Series(heat_accl_values, index=tsb_df['date']))

if __name__ == "__main__":
    records_df, metadata_df = preprocess_fit_files('data/fit')
    tsb_df = calculate_tsb(metadata_df)
    convert_coordinates(records_df)
    add_weather_data(records_df)
    calculate_grade_adjusted_speed(records_df)
    add_rolling_averages(records_df)
    add_tsb(records_df, tsb_df)
    calculate_kj(records_df)
    calculate_heat_index(records_df)
    calculate_wind_chill(records_df)
    calculate_sun_angle(records_df)
    add_weather_metadata(records_df, metadata_df)
    add_heat_acclimation(records_df, metadata_df, tsb_df)
    records_df.to_csv('data/records_df.csv', index=False)
