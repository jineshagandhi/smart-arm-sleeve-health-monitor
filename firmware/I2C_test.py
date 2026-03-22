import machine
import time

# I2C Bus 0 setup (matching your main code)
# Using the corrected pin assignments for I2C0: SDA=GP4 (Pin 6), SCL=GP5 (Pin 7)
# Note: You can also use freq=100000 here for stability if you plan to use it later.
i2c = machine.I2C(0, scl=machine.Pin(5), sda=machine.Pin(4), freq=400000)

print('Scanning I2C bus...')
devices = i2c.scan()

if devices:
    print('✅ Found I2C devices at addresses:')
    for device in devices:
        print(f'  - Hex: {hex(device)}, Decimal: {device}')
else:
    print('❌ No I2C devices found.')
    print('Please check your wiring, VCC/GND, and the pull-up resistors (VCC to SDA, VCC to SCL).')