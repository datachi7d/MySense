<img src="images/MySense-logo.png" align=right width=100>

# Adafruit SHT31 temp/humidity I2C sensor
Latest Sensirion temperature/humidity sensor I2C chip/sensor.

## STATUS
alpha test 2017/02/26

## DESCRIPTION
Adafruit SHT31 or other manufacturer. Make sure to order it with connector board. The chip is rather small.
<img src="images/SHT31.png" align=left width=100>
rel. humidity (rh,%), temperature (temp,C) sensor.
The chip is very precise And might be a good alternative to DHT or BME sensor. It interfaces to the I2C-bus of eg the Pi.

* SHT31 with connection board AliExpress € 2.85.

## References
* git clone https://github.com/ralf1070/Adafruit_Python_SHT31
* https://www.sensirion.com/en/environmental-sensors/humidity-sensors/digital-humidity-sensors-for-various-applications/
* https://www.sensirion.com/fileadmin/user_upload/customers/sensirion/Dokumente/0_Datasheets/Humidity/Sensirion_Humidity_Sensors_SHT3x_Datasheet_digital.pdf

## Hardware installation

### Module libraries
From the Adafruit_Python_SHT31 you need to install the Adafruit_SHT31.py as library in the (cloned) directory Adafruit_Python_SHT31.

Ready the Pi for i2c-bus:
```bash
    sudo apt-get install i2c-tools
    sudo apt-get python-smbus
    git clone https://github.com/ralf1070/Adafruit_Python_SHT31
    cd Adafruit_Python_SHT31; sudo python setup.py install
    git clone https://github.com/adafruit/Adafruit_Python_GPIO.git
    cd Adafruit_Python_GPIO
    sudo python setup.py install
```
For MySense you need only to install the Adafruit python GPIO or use `INSTALL.sh SHT31` script.

### HW Configuration
When selecting the I2C address, it defaults to [0x44] if the pin 5 on the circuit board (SDO) is connected to GND and [0x44] if connected to VDD (default).

GrovePi defines the pins to use if you use a GrovePi+ shield (€ 35.-).

signal   |Pi pin|GrovePi |wire  |pin SHT31
---------|------|------- |------|---------
V 5      |pin 2 |pin 2 V |red   |Vin pin
Data SDA |pin 3 |pin 3 S1|yellow|SDI pin
Clock SCL|pin 5 |pin 4 S0|white |SCK pin
GRND     |pin 6 |pin 1 G |black |Gnd pin

Enable i2c in raspi-config (Interfacing Options) and run `sudo i2cdetect -y 1`
You should see eg '44' is new address in row '40' (the address 0x44)

### HW Test
```bash
    python ./Adafruit_SHT31_Example.py
```

## MySense and SHT31 configuration
Enable input for the section [sht31] in the configuration/init file MySense.conf.
Default the i2c address is 0x44. Set i2c in the section to another hex value if needed.

To avoid condense  the MySense SHT31 driver will startup with heating the sensor for 5 seconds.
On the first read the temperature read maybe 2.5 degrees off.
On a read of 'not a number' or on values not in the normal range the heater will be put again for 5 seconds.

### TEST
Test with the command `python My_SHT31.py` to see if it works within MySense. You can comment the Conf['sync'] (if true do not run in multi thread mode) and Conf['debug'] in the script if needed so. To kill the process use `<cntrl>Z and kill %1` in stead of console interrupt (`<cntrl>c`).

### TUNING
With Conf['interval'] one can fiddle with the frequency of sensor readings and as so with the sliding average calculation of the window (Conf['bufsize']).
