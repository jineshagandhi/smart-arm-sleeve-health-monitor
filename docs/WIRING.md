# Hardware Wiring Guide

## Components Required

| # | Component | Quantity | Notes |
|---|-----------|----------|-------|
| 1 | Raspberry Pi Pico W | 1 | Main microcontroller |
| 2 | MAX30102 Pulse Oximeter | 1 | I2C interface |
| 3 | DS18B20 Temperature Sensor | 1 | OneWire interface, waterproof probe |
| 4 | MQ-135 Gas Sensor | 1 | Analog output |
| 5 | LED (Green) | 1 | Status: Good |
| 6 | LED (Yellow) | 1 | Status: Moderate |
| 7 | LED (Red) | 1 | Status: Risk |
| 8 | Passive Buzzer | 1 | Critical alarm |
| 9 | 4.7k Ohm Resistor | 1 | Pull-up for DS18B20 |
| 10 | 220 Ohm Resistors | 3 | Current limiting for LEDs |
| 11 | Breadboard | 1 | For prototyping |
| 12 | Jumper Wires | ~20 | Male-to-male |

## Wiring Diagram

### MAX30102 (Pulse Oximeter) - I2C Bus 0

```
MAX30102        Pico W
--------        ------
VIN  --------  3V3 (Pin 36)
GND  --------  GND (Pin 38)
SDA  --------  GP4 (Pin 6)
SCL  --------  GP5 (Pin 7)
```

### DS18B20 (Temperature Sensor) - OneWire

```
DS18B20         Pico W
-------         ------
VCC (Red)  ---  3V3 (Pin 36)
GND (Black) --  GND (Pin 38)
DATA (Yellow) - GP1 (Pin 2)
                  |
              [4.7k Ohm]
                  |
                3V3

Note: 4.7k pull-up resistor between DATA and 3V3 is REQUIRED
```

### MQ-135 (Air Quality Sensor) - Analog

```
MQ-135          Pico W
------          ------
VCC  --------  VBUS (Pin 40) or 5V
GND  --------  GND (Pin 38)
AOUT --------  GP26/ADC0 (Pin 31)
```

> Note: MQ-135 needs 5V for the heater. Use VBUS pin (USB 5V).

### LEDs and Buzzer - Digital Output

```
Green LED       Pico W
---------       ------
Anode (+) --[220R]-- GP16 (Pin 21)
Cathode (-) -------- GND

Yellow LED
----------
Anode (+) --[220R]-- GP17 (Pin 22)
Cathode (-) -------- GND

Red LED
-------
Anode (+) --[220R]-- GP18 (Pin 24)
Cathode (-) -------- GND

Buzzer
------
(+)  --------  GP19 (Pin 25)
(-)  --------  GND
```

## Pin Summary Table

| Pico W Pin | GPIO | Function | Component |
|-----------|------|----------|-----------|
| Pin 2 | GP1 | OneWire Data | DS18B20 |
| Pin 6 | GP4 | I2C0 SDA | MAX30102 |
| Pin 7 | GP5 | I2C0 SCL | MAX30102 |
| Pin 21 | GP16 | Digital Out | Green LED |
| Pin 22 | GP17 | Digital Out | Yellow LED |
| Pin 24 | GP18 | Digital Out | Red LED |
| Pin 25 | GP19 | Digital Out | Buzzer |
| Pin 31 | GP26 | ADC0 | MQ-135 |
| Pin 36 | 3V3 | Power | Sensors |
| Pin 38 | GND | Ground | All |
| Pin 40 | VBUS | 5V Power | MQ-135 |

## Troubleshooting

1. **MAX30102 not detected**: Run `I2C_test.py` to scan the I2C bus. Expected address: `0x57`
2. **DS18B20 no reading**: Verify the 4.7k pull-up resistor is connected between DATA and 3V3
3. **MQ-135 reading 0**: Allow 24-48 hours of burn-in time for a new sensor; ensure 5V supply
4. **LEDs not lighting**: Check LED polarity (longer leg = anode = +)
