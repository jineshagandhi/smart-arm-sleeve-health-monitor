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
# Import the custom ML models
from health_model import predict_health_status # Original Physiological Model
from tflite_env_model import get_env_status # NEW: Environmental TFLite Model Helper
from tflite_env_model import ENVIRONMENT_RISK_MAP # Import risk map for fusion

# --- GLOBAL CONFIGURATION ---
I2C_FREQ = 100000
TEMP_PIN = 1
GAS_PIN = 26

# --- PIN DEFINITIONS FOR OUTPUTS ---
LED_GREEN_PIN = 16
LED_YELLOW_PIN = 17
LED_RED_PIN = 18
BUZZER_PIN = 19

# --- INITIALIZE OUTPUT PINS ---
led_green = None
led_yellow = None
led_red = None
buzzer = None

# --- CONSTANTS FOR ALARM LOGIC ---
SPO2_CRITICAL_THRESHOLD = 94.0 # Buzzer alarms if SpO2 falls below this
TEMP_CRITICAL_THRESHOLD = 30.0 # Buzzer alarms if Temperature exceeds this
# MAPPING FOR RISK FUSION: Good=0, Moderate=1, Risk/Hazard=2
PHYSIO_RISK_MAP = {"Good": 0, "Moderate": 1, "Risk": 2}
FUSED_STATUS_LABELS = ["Good", "Moderate", "Risk"]

# --- FUNCTIONS ---

def calculate_bp(bpm):
    """
    Estimates Systolic and Diastolic Blood Pressure (BP)
    using an empirical formula based on Heart Rate (BPM).
    """
    systolic = 109.0 + (0.4 * bpm)
    diastolic = 65.0 + (0.2 * bpm)
    
    # Simple bounds check
    if systolic > 200.0: systolic = 200.0
    if diastolic > 120.0: diastolic = 120.0
        
    return systolic, diastolic

def led_control(status):
    """Sets the LED status based on the FUSED ML prediction (Good, Moderate, Risk)."""
    # Turn all LEDs OFF first
    if led_green: led_green.value(0)
    if led_yellow: led_yellow.value(0)
    if led_red: led_red.value(0)
    
    if status == "Good" and led_green:
        led_green.value(1)
    elif status == "Moderate" and led_yellow:
        led_yellow.value(1)
    elif status == "Risk" and led_red:
        led_red.value(1)
        
def buzzer_alarm(state):
    """Turns the buzzer ON (1) or OFF (0)."""
    if buzzer:
        buzzer.value(state)

def fuse_predictions(physio_status, env_status):
    """
    NEW: Fusion Logic. The final status is the highest risk between the two models.
    Risk Levels: 0 (Good/Safe) < 1 (Moderate/Warning) < 2 (Risk/Hazard)
    """
    # Get numeric risk scores
    physio_risk = PHYSIO_RISK_MAP.get(physio_status, 0)
    
    # Env status can be "Safe", "Warning", or "Hazard". We map that to 0, 1, or 2.
    env_risk = ENVIRONMENT_RISK_MAP.get(env_status, 0) 
    
    # Select the maximum risk score
    max_risk = max(physio_risk, env_risk)
    
    # Return the corresponding label
    return FUSED_STATUS_LABELS[max_risk]

# --- 1. Initialization and Setup ---

# 1.1 MAX30102 (I2C) Setup
try:
    # Initialize I2C Bus 0 on the correct pins (GP4 SDA, GP5 SCL)
    i2c = machine.I2C(0, scl=machine.Pin(5), sda=machine.Pin(4), freq=I2C_FREQ)
    
    # --- I2C SCAN FOR DIAGNOSTICS ---
    devices = i2c.scan()
    if devices:
        print(f"I2C Scan: ✅ Found devices at addresses: {[hex(d) for d in devices]}")
        # Assuming the MAX30102 is at a scanned address, attempt initialization
        sensor_max = MAX30102(i2c=i2c)
        print("MAX30102: Initializing sensor...")
    else:
        print("I2C Scan: ❌ No devices found. Check VCC/GND/SCL/SDA wiring.")
        sensor_max = None
except Exception as e:
    print(f"❌ MAX30102 Error: {e}")
    sensor_max = None 

# 1.2 DS18B20 (One-Wire) Setup
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

# 1.3 MQ-135 (ADC) Setup
try:
    # Use ADC(26) for GP26 or ADC(0) for ADC pin 0 on Pico board
    adc = machine.ADC(26) 
    sensor_gas = mq135.MQ135(adc) 
    print("MQ-135: ✅ Air quality sensor initialized on ADC0 (GP26).")
except Exception as e:
    print(f"❌ MQ-135 Error: {e}. Check wiring and ADC pin definition.")
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
CALIBRATION_INTERVAL = 5 # 5s for model prediction and environmental read

last_env_read = time.time()
temp_c = 0.0
gas_ppm = 0.0

# NEW STATUS VARIABLES
physio_status = "Awaiting Data"
env_status = "Awaiting Data"
fused_status = "Awaiting Data"

systolic_bp = 0.0
diastolic_bp = 0.0

# BPM Filtering constants (used to discard noise/artifacts)
MIN_BPM = 40.0
MAX_BPM = 120.0


try:
    while True:
        # --- 2.1 MAX30102 Reading (High Frequency) ---
        if sensor_max:
            # We only read if sensor_max initialized correctly
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
                try:
                    sensor_temp.convert_temp()
                    time.sleep_ms(750)
                    new_temp = sensor_temp.read_temp(roms[0])
                    if new_temp is not None:
                        temp_c = new_temp
                except Exception as e:
                    print(f"DS18B20 Read Error: {e}", end='\r')
            
            if sensor_gas:
                # Assuming constant humidity of 35% for corrected PPM
                gas_ppm = sensor_gas.get_corrected_ppm(temp_c, 35)
            
            # --- MODEL PREDICTION: PHYSIOLOGICAL (HEALTH_MODEL) ---
            if (hr_valid and spo2_valid and hr >= MIN_BPM and hr <= MAX_BPM): 
                # F0=HR, F1=SpO2, F2=SBP, F3=DBP, F4=0.0
                physio_features = [hr, spo2, systolic_bp, diastolic_bp, 0.0] 
                physio_status, _ = predict_health_status(physio_features)
            else:
                if hr > MAX_BPM or hr < MIN_BPM:
                    physio_status = "BPM Noise"
                else:
                    physio_status = "Calibrating"
            
            # --- MODEL PREDICTION: ENVIRONMENTAL (TFLITE MODEL) ---
            if temp_c != 0.0 and gas_ppm != 0.0:
                env_status, env_risk_score = get_env_status(temp_c, gas_ppm)
            else:
                env_status = "Calibrating"
            
            # --- FUSION LOGIC ---
            if "Noise" not in physio_status and "Calibrating" not in physio_status:
                fused_status = fuse_predictions(physio_status, env_status)
            else:
                fused_status = physio_status
            
            # --- LED CONTROL ---
            led_control(fused_status)

            last_env_read = time.time()
            
            # --- Print Combined Results ---
            print("\n----------------- FUSED ML DATA (5s window) -----------------")
            print(f"🌡️ Temperature: {temp_c:.1f} °C | 💨 Air Quality: {gas_ppm:.0f} PPM")
            print(f"❤️ Physio Model Status: {physio_status}")
            print(f"🌳 Env Model Status:    {env_status} (Thresholds)")
            print(f"🧠 **FUSED Health Status:** {fused_status}")
            print("-------------------------------------------------------------")


        # --- 2.3 ALARM CHECK (CRITICAL OVERRIDE) ---
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
            max_status = f"❤️ BPM: {hr:.1f} | 🩸 SpO2: {spo2:.1f}%{bp_status} | Fused: {fused_status}"
        elif hr_valid:
            bp_status = f" | 🩺 BP: {systolic_bp:.0f}/{diastolic_bp:.0f} mmHg"
            max_status = f"❤️ BPM: {hr:.1f} | 🩸 SpO2: -- (Gathering SpO2 data){bp_status}"
        elif sensor_max:
            max_status = "Gathering data... Place/Keep finger still."
        else:
            max_status = "MAX30102 Disabled/Failed. Check wiring/I2C scan."
            
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
    if buzzer: buzzer.value(0)
