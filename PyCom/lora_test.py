try:
  from Config import Network
  from Config import dev_eui, app_eui, app_key
  if Network != 'TTN' and not (app_key or app_eui or dev_eui):
     raise OSError('No LoRa defined')
  from lora import LORA
except:
  raise OSError('No LoRa config or libs defined')

import sys
import struct
from time import time, sleep

# Turn off hearbeat LED
import pycom
pycom.heartbeat(False)

info = None
n = None
def SendInfo(port,data):
  print("info requested")
  if not data: return
  if (not info) or (not n): return
  print("Sent info")
  sleep(30)
  n.send(info,port=3)

n = LORA()
if not n.connect(dev_eui, app_eui, app_key,ports=2):
  print("Failed to connect to LoRaWan TTN")
  sys.exit(0)

# send first some info
# dust (None,Shiney,Nova,Plantower, ...) 4 low bits
# meteo (None,DHT11,DHT22,BME280,BME680, ...) 4 high bits
# GPS (longitude,latitude, altitude) float
# send 17 bytes

Dust = ['unknown','PPD42NS','SDS011','PMS7003']
Meteo = ['unknown','DHT11','DHT22','BME280','BME680']
try:
  from Config import meteo
except:
  meteo = 0
try:
  from Config import dust
except:
  dust = 0

try:
  from Config import useGPS, thisGPS
except:
  thisGPS = [0,0,0]

if useGPS:
  thisGPS = [50.12345,6.12345,12.34]

info = struct.pack('>BBlll',0,dust|(meteo<<4),int(thisGPS[0]*100000),int(thisGPS[1]*100000), int(thisGPS[2]*10))
print("Sending version 0, meteo %s index %d, dust %s index %d, GPS: " % (Meteo[meteo], meteo,Dust[dust],dust), thisGPS)

if not n.send(info,port=3): print("send error")
else: print('Sent info')

for cnt in range(5):
  data = struct.pack('>HHHHHHHHl', 10+cnt, 15+cnt, 20+cnt, 25+cnt, 30+cnt, 35+cnt, 40+cnt, 45+cnt, time())
  #data = base64.encodestring(data)
  # Send packet
  if not n.send(data):  # send to LoRa port 2
    print("send error")
  else: print('Sent data')
  sleep(60)
print('Done')
