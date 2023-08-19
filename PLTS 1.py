import time
import threading
from gpiozero import LED
from gpiozero.pins.mock import MockFactory
from gpiozero import Device, MCP3008
from ina219 import INA219, DeviceRangeError
from ubidots import ApiClient

# Replace with your actual Ubidots token and variable IDs
UBIDOTS_TOKEN = ""
POWER_INPUT_VAR_ID = ""
MODE_VAR_ID = ""
POWER_OUTPUT_VAR_ID = ""
SWITCHING_VAR_ID = ""
BATTERY_VAR_ID = ""

# Initialize Ubidots API client
api = ApiClient(token=UBIDOTS_TOKEN)

# Initialize GPIOZero MockFactory and Devices for MCP3008
Device.pin_factory = MockFactory()
adc_SCT013 = MCP3008(channel=1)
adc_battery = MCP3008(channel=0)

# Initialize INA219 for solar panel monitoring
SHUNT_OHMS = 0.1  # Shunt resistor value in ohms
ina_solar = INA219(SHUNT_OHMS, address=0x40)
ina_solar.configure()

# Initialize relays
relay_plts = LED(17)  # Replace with actual pin number
relay_pln = LED(18)  # Replace with actual pin number

# Function to read current from SCT013 sensor
def read_current():
    try:
        voltage = adc_SCT013.value * 3.3
        current = (voltage - 2.5) / 0.066  # Calibration factor for 100/50 mA SCT013
        return current
    except Exception as e:
        print("Error reading current:", e)
        return 0.0

# Function to read solar panel power input
def read_solar_power():
    try:
        voltage = ina_solar.voltage()
        current = ina_solar.current()
        power_input = voltage * current
        return power_input
    except Exception as e:
        print("Error reading solar power input:", e)
        return 0.0

# Function to read battery percentage
def read_battery_percentage():
    try:
        voltage = adc_battery.value * 3.3 * 5  # Voltage divider ratio 1:5
        battery_percentage = (voltage - 11.2) / (14.2 - 11.2) * 100
        return max(0, min(100, battery_percentage))
    except Exception as e:
        print("Error reading battery percentage:", e)
        return 0.0

# Function to switch power source based on conditions
def switch_power_source():
    try:
        manual_mode = api.get_variable(MODE_VAR_ID).get_values()[0]['value']
        
        battery_percentage = read_battery_percentage()
        solar_power_input = read_solar_power()
        power_output = read_current() * 220  # Convert current to power
        
        if manual_mode == "Manual":
            if power_output > 700:
                relay_plts.off()
                relay_pln.on()
                api.save_value(SWITCHING_VAR_ID, "PLN", context={"value": "Manual"})
            else:
                relay_plts.on()
                relay_pln.off()
                api.save_value(SWITCHING_VAR_ID, "PLTS", context={"value": "Manual"})
        else:
            if battery_percentage > 50:
                relay_plts.on()
                relay_pln.off()
                api.save_value(SWITCHING_VAR_ID, "PLTS", context={"value": "Auto"})
            elif battery_percentage < 20:
                relay_plts.off()
                relay_pln.on()
                api.save_value(SWITCHING_VAR_ID, "PLN", context={"value": "Auto"})
            elif solar_power_input > 700:
                relay_plts.off()
                relay_pln.on()
                api.save_value(SWITCHING_VAR_ID, "PLN", context={"value": "Auto"})
            else:
                relay_plts.on()
                relay_pln.off()
                api.save_value(SWITCHING_VAR_ID, "PLTS", context={"value": "Auto"})
        
        api.save_value(POWER_OUTPUT_VAR_ID, power_output)
        api.save_value(BATTERY_VAR_ID, battery_percentage)
        api.save_value(POWER_INPUT_VAR_ID, solar_power_input)
    except Exception as e:
        print("Error switching power source:", e)

# Main loop to periodically switch power source
while True:
    switch_power_source()
    time.sleep(5)  # Adjust interval as needed
