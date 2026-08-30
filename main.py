import time
import math
from machine import Pin, I2C, UART
import bme280

# --- 1. SETUP BME280 (I2C) ---
i2c = I2C(0, scl=Pin(22), sda=Pin(21))
bme = bme280.BME280(i2c=i2c)

# --- 2. SETUP PMS7003 (UART) ---
# Pins: GPIO 16 (RX) and GPIO 17 (TX) at 9600 baud rate
uart = UART(1, baudrate=9600, tx=Pin(17), rx=Pin(16))

def read_bme_scaled():
    """Reads temperature, pressure, and humidity from BME280."""
    raw_t, raw_p, raw_h = bme.read_compensated_data()
    temp_c = raw_t / 100.0
    press_hpa = (raw_p / 256.0) / 100.0
    hum_pct = raw_h / 1024.0
    return temp_c, press_hpa, hum_pct

def calculate_altitude(pressure_hpa, p_reference):
    """Calculates relative altitude in meters based on ground pressure."""
    if pressure_hpa <= 0 or p_reference <= 0:
        return 0.0
    return 44330.0 * (1.0 - math.pow(pressure_hpa / p_reference, (1.0 / 5.255)))

def read_pms7003():
    """Reads 32-byte frame from PMS sensor and returns isolated particle categories."""
    if uart.any() >= 32:
        buffer = uart.read(32)
        # Check start frame bytes (0x42, 0x4D)
        if buffer[0] == 0x42 and buffer[1] == 0x4D:
            pm1_0 = (buffer[10] << 8) | buffer[11]
            pm2_5 = (buffer[12] << 8) | buffer[13]
            pm10_0 = (buffer[14] << 8) | buffer[15]

            # Differentiate particle sizes
            ultrafine_smoke = pm1_0                  # < 1.0 um (smoke, soot, exhaust)
            fine_dust = max(0, pm2_5 - pm1_0)        # 1.0 um - 2.5 um (fine dust, cooking fumes)
            coarse_pollen = max(0, pm10_0 - pm2_5)   # 2.5 um - 10.0 um (pollen, heavy dust)

            return pm2_5, ultrafine_smoke, fine_dust, coarse_pollen

    return None, None, None, None

# --- INITIALIZATION & CALIBRATION ---
print("Calibrating ground baseline pressure...")
time.sleep(1)

_, P_GROUND, _ = read_bme_scaled()
print("Ground Baseline Pressure set to: {:.2f} hPa".format(P_GROUND))
print("--------------------------------------------------")

# --- MAIN LOOP ---
while True:
    try:
        # Read Environmental Data
        temp_c, press_hpa, hum_pct = read_bme_scaled()
        altitude_m = calculate_altitude(press_hpa, P_GROUND)

        # Read Particulate Matter Data
        pm25_total, smoke, fine_dust, pollen = read_pms7003()

        # Format Sensor Readings Output
        if pm25_total is not None:
            air_str = "PM2.5 Total: {} ug/m3 | Smoke/Soot (<1um): {} ug/m3 | Fine Dust (1-2.5um): {} ug/m3 | Pollen (2.5-10um): {} ug/m3".format(
                pm25_total, smoke, fine_dust, pollen
            )
        else:
            air_str = "Air Sensor: Waiting for data..."

        print("Temp: {:.2f} C | Press: {:.2f} hPa | Alt: {:.2f} m | Hum: {:.2f}%".format(
            temp_c, press_hpa, altitude_m, hum_pct
        ))
        print(air_str)
        print("-" * 50)

    except Exception as e:
        print("Sensor read error:", e)

    time.sleep(1)
