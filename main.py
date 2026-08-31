import time  #library imports, time allows to code for pause/stop durations, maths for operations and advanced calculations,
import math
from machine import Pin, I2C, UART #Imports hardware controls/codes from micropython's 'machine ' library where Pin controls the physicalinput/output pins of the ESP32 , and I^2C and UART are the communication protocols of the BME280 and PMS7003 

import bme280 #imports external bme280 driver library installed on esp32#



# SETUP BME280 (I2C) 
i2c = I2C(0, scl=Pin(22), sda=Pin(21)) #specifies unit 0 to communicate w bme280, scl=serial clock line at pin22 sends a pulsing signal, sda=serial data line, carries all measured data
bme = bme280.BME280(i2c=i2c) #bme280 library connected to the i2c protocol created above

# 2. SETUP PMS7003 (UART) 
# Pins: GPIO 16 (RX) and GPIO 17 (TX) at 9600 baud rate
uart = UART(1, baudrate=9600, tx=Pin(17), rx=Pin(16)) #serial port 1 on esp32 to communicate w pms7003, 9600bits per sec transmission speed, tx=transmit pin on and rx=recieve pin on esp32




def read_bme_scaled(): #custom function to convert raw values to real data
    #Reads temperature, pressure, and humidity from BME280 
    raw_t, raw_p, raw_h = bme.read_compensated_data() #requests the values from the sensor library
    temp_c = raw_t / 100.0            
    press_hpa = (raw_p / 256.0) / 100.0  #(raw to hPa)
    hum_pct = raw_h / 1024.0   #(raw to actual % value)
    return temp_c, press_hpa, hum_pct 



def calculate_altitude(pressure_hpa, p_reference):  
    #Calculates relative altitude in m based on ground pressure
    if pressure_hpa <= 0 or p_reference <= 0: #if data returns as 0 or negative, instead of crashing it returns as 0.0
        return 0.0
    return 44330.0 * (1.0 - math.pow(pressure_hpa / p_reference, (1.0 / 5.255))) #the international hypsometric barometric formula to calculate altitude using the ground and relative pressure values




def read_pms7003():
    #Reads 32byte frame from PMS sensor and returns isolated particle categories
    if uart.any() >= 32:   #makes sure data arrives fully in 32bytes 
        buffer = uart.read(32) #reads the 32bytes into this variable
        #Check start frame bytes (0x42, 0x4D)
        if buffer[0] == 0x42 and buffer[1] == 0x4D:  #marks first two bytes, ascii 'BM', to ensure 32byte package
            pm1_0 = (buffer[10] << 8) | buffer[11]
            pm2_5 = (buffer[12] << 8) | buffer[13]
            pm10_0 = (buffer[14] << 8) | buffer[15]

            # Differentiate particle sizes
            ultrafine_smoke = pm1_0                  # < 1.0 um (smoke, soot, exhaust)
            fine_dust = max(0, pm2_5 - pm1_0)        # 1.0 um - 2.5 um (fine dust, cooking fumes)    #isolates specific concentrations
            coarse_pollen = max(0, pm10_0 - pm2_5)   # 2.5 um - 10.0 um (pollen, heavy dust)

            return pm2_5, ultrafine_smoke, fine_dust, coarse_pollen

    return None, None, None, None  #prevents crashing






#INITIALIZATION & CALIBRATION
print("Calibrating ground baseline pressure..."). #initialization cooldown
time.sleep(1)

_, P_GROUND, _ = read_bme_scaled()   #reads ground pressure, excludes other data
print("Ground Baseline Pressure set to: {:.2f} hPa".format(P_GROUND))
print("--------------------------------------------------")

#MAIN LOOP-continous until esp unplugged
while True: #prevents crashing
    try:
        # Read Environmental Data
        temp_c, press_hpa, hum_pct = read_bme_scaled()
        altitude_m = calculate_altitude(press_hpa, P_GROUND)

        # Read PMatter data
        pm25_total, smoke, fine_dust, pollen = read_pms7003()

        # Format Sensor Readings Output
        if pm25_total is not None:
            air_str = "PM2.5 Total: {} ug/m3 | Smoke/Soot (<1um): {} ug/m3 | Fine Dust (1-2.5um): {} ug/m3 | Pollen (2.5-10um): {} ug/m3".format(
                pm25_total, smoke, fine_dust, pollen)
        else:
            air_str = 'Air Sensor: Waiting for data...'   #to prevent crashing/nodata

        print("Temp: {:.2f} C | Press: {:.2f} hPa | Alt: {:.2f} m | Hum: {:.2f}%".format(
            temp_c, press_hpa, altitude_m, hum_pct))
        print(air_str)
        print("-" * 50) #formatting

    except Exception as e:
        print("Sensor read error:", e)
#incase of external problems
    time.sleep(1) #sampling freq in sec
