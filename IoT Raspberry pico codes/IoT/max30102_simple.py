# max30102_simple.py
from machine import I2C
import time

class MAX30102:
    def __init__(self, i2c, addr=0x57):
        self.i2c = i2c
        self.addr = addr
        self.reset()
        self.setup()

    def reset(self):
        # Reset the sensor
        self.write_reg(0x09, 0x40)  # reset bit
        time.sleep(0.1)

    def write_reg(self, reg, val):
        self.i2c.writeto_mem(self.addr, reg, bytes([val]))

    def read_reg(self, reg, nbytes=1):
        return self.i2c.readfrom_mem(self.addr, reg, nbytes)

    def setup(self):
        # Set LED pulse amplitude
        self.write_reg(0x09, 0x03)  # SpO2 config, sample rate, LED pulse width
        self.write_reg(0x0A, 0x27)  # LED1 and LED2 pulse amplitude
        self.write_reg(0x06, 0x40)  # FIFO config

    def read_fifo(self):
        # Read 6 bytes from FIFO
        data = self.read_reg(0x07, 6)
        red = (data[0] << 16) | (data[1] << 8) | data[2]
        ir = (data[3] << 16) | (data[4] << 8) | data[5]
        return red, ir

    def available(self):
        # Check if data is available
        val = self.read_reg(0x04)[0]
        return (val & 0x80) != 0  # Check sample ready flag

