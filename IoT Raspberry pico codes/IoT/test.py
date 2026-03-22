import machine
import time
import math
# Import MAX30102 drivers
from max30102 import MAX30102
from hrcalc import calc_hr_and_spo2
# Import DS18B20 drivers
import onewire
import ds18x20
# Import MQ-135 driver
import mq135
# Import the custom ML model
from health_model import predict_health_status 

# --- GLOBAL CONFIGURATION ---
I2C_FREQ = 100000 
TEMP_PIN = 1 
GAS_PIN = 26 

# --- NEW PIN DEFINITIONS FOR OUTPUTS ---
# IMPORTANT: These pins MUST be connected with 220-330 Ohm resistors!
LED_GREEN_PIN = 16 
LED_YELLOW_PIN = 17 
# Using GP12 (Physical Pin 16) for Red LED
LED_RED_PIN = 12 
BUZZER_PIN = 19 

# --- INITIALIZE OUTPUT PINS (DONE LATER IN SECTION 1.4) ---
led_green = None
led_yellow = None
led_red = None
buzzer = None

# --- CONSTANTS FOR ALARM LOGIC ---
SPO2_CRITICAL_THRESHOLD = 94.0 # Buzzer alarms if SpO2 falls below this
TEMP_CRITICAL_THRESHOLD = 30.0 # Buzzer alarms if Temperature exceeds this

# --- GAS AQI SCORING CONSTANTS ---
# PPM values used to score general air quality from 0 (Excellent) to 100 (Hazardous)
PPM_GOOD_THRESHOLD = 450.0  # PPM below this gives a score near 0
PPM_HAZARDOUS_THRESHOLD = 1500.0 # PPM at or above this gives a score of 100

# --- FUNCTIONS ---

def calculate_bp(bpm):
    """
    Estimates Systolic and Diastolic Blood Pressure (BP)
    using an empirical formula based on Heart Rate (BPM).
    NOTE: PPG-derived BP is an approximation and should not be used for medical diagnosis.
    """
    # Use physiologically plausible approximations for estimation
    systolic = 109.0 + (0.4 * bpm)
    diastolic = 65.0 + (0.2 * bpm)
    
    # Simple bounds check
    if systolic > 200.0: systolic = 200.0
    if diastolic > 120.0: diastolic = 120.0
        
    return systolic, diastolic

def led_control(status):
    """Sets the LED status based on the ML prediction (Good, Moderate, Risk)."""
    # Turn all LEDs OFF first
    if led_green: led_green.value(0)
    if led_yellow: led_yellow.value(0)
    if led_red: led_red.value(0)
    
    if status == "Good":
        if led_green: led_green.value(1)
    elif status == "Moderate":
        if led_yellow: led_yellow.value(1)
    elif status == "Risk" or status == "BPM Noise (Keep finger still!)": # Keep red LED on for risk and noise
        if led_red: led_red.value(1)
        
def buzzer_alarm(state):
    """Turns the buzzer ON (1) or OFF (0)."""
    if buzzer:
        buzzer.value(state)

def calculate_aqs(gas_ppm):
    """
    Converts raw PPM (from MQ-135) to a simple 0-100 Air Quality Score (AQS).
    0 = Excellent (low pollution), 100 = Hazardous (high pollution).
    """
    if gas_ppm < PPM_GOOD_THRESHOLD:
        return 0
    
    # Map PPM between the good and hazardous thresholds to 0-100 score
    if gas_ppm < PPM_HAZARDOUS_THRESHOLD:
        # Linear interpolation: Score = 100 * (PPM - Low) / (High - Low)
        aqs = 100 * (gas_ppm - PPM_GOOD_THRESHOLD) / (PPM_HAZARDOUS_THRESHOLD - PPM_GOOD_THRESHOLD)
        return int(min(aqs, 99)) # Ensure it doesn't exceed 99 before 1500 PPM
    else:
        return 100

# --- 1. Initialization and Setup ---

# 1.1 MAX30102 (I2C) Setup (unchanged)
try:
    i2c = machine.I2C(0, scl=machine.Pin(5), sda=machine.Pin(4), freq=I2C_FREQ)
    sensor_max = MAX30102(i2c=i2c)
    print("MAX30102: Initializing sensor...")
except Exception as e:
    print(f"❌ MAX30102 Error: {e}")
    sensor_max = None 

# 1.2 DS18B20 (One-Wire) Setup (unchanged)
try:
    ds_pin = machine.Pin(TEMP_PIN)
    ds_bus = onewire.OneWire(ds_pin)
    sensor_temp = ds18x20.DS18X20(ds_bus)
    roms = sensor_temp.scan()
    if roms:
        print(f"DS18B20: ✅ Found {len(roms)} temperature sensor(s).")
    else:
        print("DS18B20: ❌ No sensor found. Check 4.7kΩ pull-up resistor (Data to 3.3V).")
        sensor_temp = None
except Exception as e:
    print(f"❌ DS18B20 Error: {e}")
    sensor_temp = None

# 1.3 MQ-135 (ADC) Setup (unchanged)
try:
    adc = machine.ADC(0) 
    sensor_gas = mq135.MQ135(adc) 
    print("MQ-135: ✅ Air quality sensor initialized on ADC0 (GP26).")
except Exception as e:
    print(f"❌ MQ-135 Error: {e}. Check wiring and try defining ADC pin as 'machine.ADC(26)' or 'machine.ADC(0)'.")
    sensor_gas = None

# 1.4 LED and Buzzer Setup
try:
    led_green = machine.Pin(LED_GREEN_PIN, machine.Pin.OUT)
    led_yellow = machine.Pin(LED_YELLOW_PIN, machine.Pin.OUT)
    led_red = machine.Pin(LED_RED_PIN, machine.Pin.OUT)
    buzzer = machine.Pin(BUZZER_PIN, machine.Pin.OUT)
    # Turn off all outputs initially
    led_green.value(0)
    led_yellow.value(0)
    led_red.value(0)
    buzzer.value(0)
    print("Outputs: ✅ LEDs and Buzzer initialized.")
except Exception as e:
    print(f"❌ Output Pin Error: {e}")
    led_green, led_yellow, led_red, buzzer = None, None, None, None


print("--------------------------------------------------")

# --- 2. Main Loop Variables and Settings ---
ir_data = []
red_data = []
SAMPLES_TO_READ = 100
CALIBRATION_INTERVAL = 5 # 5s for faster testing

last_env_read = time.time()
temp_c = 0.0
gas_ppm = 0.0
air_quality_score = 0
health_status = "Awaiting Data"
systolic_bp = 0.0
diastolic_bp = 0.0

# BPM Filtering constants (used to discard noise/artifacts)
MIN_BPM = 40.0
MAX_BPM = 120.0


try:
    while True:
        # --- 2.1 MAX30102 Reading (High Frequency) ---
        if sensor_max:
            red_buf, ir_buf = sensor_max.read_sequential(amount=SAMPLES_TO_READ)
            ir_data.extend(ir_buf)
            red_data.extend(red_buf)
            hr, hr_valid, spo2, spo2_valid = calc_hr_and_spo2(ir_data, red_data)
            
            # Calculate Blood Pressure from Heart Rate
            if hr_valid:
                systolic_bp, diastolic_bp = calculate_bp(hr)
            else:
                systolic_bp, diastolic_bp = 0.0, 0.0

            ir_data = ir_data[50:]
            red_data = red_data[50:]
        else:
            hr, hr_valid, spo2, spo2_valid = 0, False, 0, False
            time.sleep(0.1)

        # --- 2.2 DS18B20, MQ-135, and ML Model (Low Frequency) ---
        if time.time() - last_env_read >= CALIBRATION_INTERVAL:
            
            # Read environmental sensors
            if sensor_temp and roms:
                sensor_temp.convert_temp()
                time.sleep_ms(750)
                new_temp = sensor_temp.read_temp(roms[0])
                if new_temp is not None:
                    temp_c = new_temp
            
            if sensor_gas:
                gas_ppm = sensor_gas.get_corrected_ppm(temp_c, 35)
                # Calculate the custom Air Quality Score
                air_quality_score = calculate_aqs(gas_ppm)
            
            # --- MODEL PREDICTION (BPM, SpO2, SBP, DBP) ---
            if (hr_valid and spo2_valid and temp_c != 0.0 and 
                hr >= MIN_BPM and hr <= MAX_BPM): 
                
                # F0=HR, F1=SpO2, F2=SBP, F3=DBP, F4=0.0
                features = [hr, spo2, systolic_bp, diastolic_bp, 0.0] 
                health_status, _ = predict_health_status(features)
                
            else:
                if hr > MAX_BPM or hr < MIN_BPM:
                    health_status = "BPM Noise (Keep finger still!)"
                else:
                    health_status = "Calibrating Sensors"

            # --- LED CONTROL ---
            led_control(health_status)

            last_env_read = time.time()
            
            # --- Print Environmental & ML Results ---
            print("\n----------------- ENV & ML DATA -----------------")
            # Displaying AQS (0-100) instead of raw PPM
            print(f"🌡 Temperature: {temp_c:.1f} °C | 💨 Air Quality Score (AQS): {air_quality_score:.0f} (PPM: {gas_ppm:.0f})")
            print(f"🧠 *Health Status:* {health_status} (Based on 5s window)")
            print("-------------------------------------------------")


        # --- 2.3 ALARM CHECK ---
        is_alarming = False
        
        # Check SpO2 alarm (requires a valid reading)
        if spo2_valid and spo2 < SPO2_CRITICAL_THRESHOLD:
            is_alarming = True
        
        # Check Temperature alarm (requires a valid reading)
        if temp_c > TEMP_CRITICAL_THRESHOLD:
            is_alarming = True
            
        buzzer_alarm(1 if is_alarming else 0)


        # --- 2.4 Consolidated Output (MAX30102) ---
        if hr_valid and spo2_valid:
            bp_status = f" | 🩺 BP: {systolic_bp:.0f}/{diastolic_bp:.0f} mmHg"
            max_status = f"❤ BPM: {hr:.1f} | 🩸 SpO2: {spo2:.1f}%{bp_status} | Health: {health_status}"
        elif hr_valid:
            bp_status = f" | 🩺 BP: {systolic_bp:.0f}/{diastolic_bp:.0f} mmHg"
            max_status = f"❤ BPM: {hr:.1f} | 🩸 SpO2: -- (Gathering SpO2 data){bp_status}"
        elif sensor_max:
            max_status = "Gathering data... Place/Keep finger still."
        else:
            max_status = "MAX30102 Disabled/Failed."
            
        print(f"STATUS: {max_status}", end='\r')


except KeyboardInterrupt:
    print("\nProgram stopped by user.")
finally:
    if sensor_max:
        try:
            sensor_max.shutdown()
            print("\nMAX30102 shutdown complete.")
        except AttributeError:
            pass
    
    # --- Final Shutdown of Outputs ---
    if led_green: led_green.value(0)
    if led_yellow: led_yellow.value(0)
    if led_red: led_red.value(0)
    if buzzer: buzzer.value(0)