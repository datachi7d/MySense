#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Contact Teus Hagen webmaster@behouddeparel.nl to report improvements and bugs
# 
# Copyright (C) 2017, Behoud de Parel, Teus Hagen, the Netherlands
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

# $Id: MyTTN_MQTT.py,v 1.2 2017/12/16 21:10:52 teus Exp teus $

# Broker between TTN and some  data collectors: luftdaten.info map and MySQL DB

# module mqtt: git clone https://github.com/eclipse/paho.mqtt.python.git
# cd paho.mqtt.python ; python setup.py install
# broker server: Debian: apt-get install mqtt

""" Download measurements from TTN MQTTT server:
    Subscribe to measurements from a Mosquitto Broker server
    e.g.
    Publish measurements as client to luftdaten.info and MySQL vuurwerk DB
    This is dedicated to TTN LoRa RIVM records at Fireworks 2017 project time.
    One may need to change payload and TTN record format!
"""
try:
    import MyLogger
    import dateutil.parser as dp
    import datetime
    import sys, os
    import json
    import socket
    import re
    from time import time, sleep
    socket.setdefaulttimeout(60)
    import paho.mqtt.client as mqtt
except ImportError as e:
    sys.stderr.write("One of the import modules not found: %s\n" % e)
    exit(1)

waiting = False          # waiting for telegram
mid = None               # for logging: message ID
telegrams = []           # telegram buffer, max length is 100     
ErrorCnt = 0             # connectivit error count, slows down, >20 reconnect, >40 abort
PingTimeout = 0          # last time ping request was sent

# TTN working command line example
# mosquitto_sub -v -h eu.thethings.network -p 1883 -u 20170921597128 -P 'ttn-account-v2.ZJvoRKh3XkHsegybn_hADOOGEglqf6CCGAhqLUJLrXA'  -t '+/devices/+/up' -v

# configurable options
__options__ = [ 'input',       # output enables
                'hostname','port', 'user','password',
                'dust', 'meteo'  # classes field names coming from TTN MQTT server
                'file', 'adminfile']

Conf = {
    'input': True,
    'hostname': 'eu.thethings.network', # server host number for mqtt broker
    'port': 1883,        # default MQTT port
    'user': 'my_user', # TTN name
    'password': 'ttn-account-v2.vFbXhUQFz35BIYQ5zm4Xqd_OOEIaXUK3JYzXEfLNZ2s',
    # credentials to access broker
    'qos' : 0,           # dflt 0 (max 1 telegram), 1 (1 telegram), or 2 (more)
    'cert' : None,       # X.509 encryption
    'topic': 'devices',  # main topic
    'prefix': 'VW_',     # prefix to unique device number, used in Api Key
    # + is a wild card in TTN
    # To Do: use reg exp
    'AppId': '+',        # regular expression to accept AppId to subscribe to
    'DevAddr': '+',      # regular expression to accept DevAddr numbers
    'timeout' : 2*60*60, # timeout for this broker
    'file': 'Dumped.json', # comment this for operation, this will read from a dump MQTT file
    'adminfile': 'VM2017devices.json', # meta identy data for sensor kits
    # 'debug': True     # use TTN record example in stead of server access
    'dust': ['pm2.5','pm10',],   # dust names we can get, SDS011, PMS7003, PPD42NS
    'meteo': ['temp','humidity','pressure',], # meteo name we get from DHT22, BME280
}

devices = {}
if 'adminfile' in Conf.keys():
    # json should be read from file
    try:
        devices = json.load(open(Conf['adminfile']))
    except:
        MySyslog.log(modulename,"ATTENT','Missing LoRa admin json file with info for all LaRa devices\n")
        # exit(1)
        MySyslog.log(modulename,"ATTENT','Using test def for pmsensor1\n")
        # example of content of admin file specified for TTN MQTT RIVM records
        devices = {
            'pmsensor1': {      # DevAddr from eg RIVM
                'GPS': {
                    'longitude': 51.12345, 'latitude': 6.12345, 'altitude': 23, },
                'label': 'Jelle', 'street': 'straatnaam en nr',
                'village': 'Venlo', 'pcode': '5888 XY',
                'province': 'Limburg', 'municipality': 'Venlo',
                'date': '20 december 2017',
                'comment': 'test device',
                'AppSKEY': 'xyz', # LoRa key from eg RIVM
                'NwkSKey': 'xyzxyz', # LoRa key from eg RIVM
                'luftdaten.info': True,     # forward to Open Data Germany?
            }
        }
        
# update ident record with info from json admin file
def updateIdent( AppId, devAddr, ident):
    if not devAddr in devices.keys():
        return ident
    if not 'geolocation' in devices[devAddr].keys():
        if 'GPS' in devices[devAddr].keys():
            devices[devAddr]['geolocation'] = str(devices[devAddr]['GPS']['longitude'])+','+str(devices[devAddr]['GPS']['latitude'])+','+str(devices[devAddr]['GPS']['altitude'])
    for item in ["geolocation",'label','village','street','pcode','province','municipality']:
        if item in devices[devAddr].keys():
            ident[item] = devices[devAddr][item]
    if ('comment' in devices[devAddr].keys()) and devices[devAddr]['comment']:
        if not 'description' in ident.keys(): ident['description'] = ''
        ident['description'] = devices[devAddr]['comment'] + '; ' + ident['description']
    return ident

# =======================================================
# post json data to a MQTT broker for nodes somewhere internet land
# =======================================================
# use telegram style

# use input file as MQTT records, used merely as restore data
def ReadFromFile(filename):
    global Conf
    if not 'fileFD' in Conf.keys():
        try:
            Conf['fileFD'] = open(Conf['file'],'r')
        except:
            MySyslog.log(modulename,"FATAL','unable to open json input file %s\n" % Conf['file'])
            exit(1)
    while(1):
        line = Conf['fileFD'].readline()
        if (not line) or (not len(line)): # EOF
            Conf['fileFD'].close()
            exit(0)
        if line.find('/up {') < 0: continue
        return( { 'topic': line[0:line.find(' ')], 'payload': line[line.find(' ')+1:] } )

# Define event callbacks
# this is multi threaded: TTN download data thread
def PubOrSub(topic,option):
    global Conf, waiting, mid, telegrams, PingTimeout, ErrorCnt
    waiting = False
    mid = None
    telegram = None
    # uncomment if TTN server does not publish records
    # following is the telegram as is expected from TTN MQTT server
    if ('debug' in Conf.keys()) and Conf['debug']:
        return ( { 
            'topic': 'pmsensors/devices/pmsensor10/up',
            'payload': '{"app_id":"pmsensors","dev_id":"pmsensor10","hardware_serial":"EEABABABBAABABAB","port":1,"counter":73,"payload_raw":"ACgALAG0ASU=","payload_fields":{"PM10":4.4,"PM25":4,"hum":29.3,"temp":23.6,"type":"SDS011"},"metadata":{"time":"2017-12-15T19:32:04.220584016Z","frequency":868.3,"modulation":"LORA","data_rate":"SF12BW125","coding_rate":"4/5","gateways":[{"gtw_id":"eui-1dee14d549d1e063","timestamp":536700428,"time":"","channel":1,"rssi":-100,"snr":6,"rf_chain":1,"latitude":51.35284,"longitude":6.154711,"altitude":40,"location_source":"registry"}],"latitude":51.353,"longitude":6.1538496,"altitude":2,"location_source":"registry"}}'
            })

    def on_connect(client, obj, rc):
        global waiting
        if rc != 0:
            MySyslog.log(modulename,'ERROR','Connection error nr: %s\n' % str(rc))
            waiting = False
            if 'fd' in Conf.keys():
                Conf['fd'] = None
            raise IOError("MQTTsub connect failure.")
        else:
            MySyslog.log(modulename,'DEBUG','Connected.\n')
            pass
    
    def on_message(client, obj, msg):
        global waiting, telegrams
        waiting = False
        try:
            if len(telegrams) > 100:    # 100 * 250 bytes
                MySyslog.log(modulename,'ERROR','Input buffer is full.\n')
                return
            # append the TTN data to local FiFo buffer
            # print str(msg.topic)
            # print str(msg.payload)
            telegrams.append( {
                'topic': msg.topic,
                # payload is unpacked by TTN: make sure to add the unpack rules TTN
                'payload': str(msg.payload),
                })
        except:
            MySyslog.log(modulename,'ERROR Except','In message.\n')
    
    def on_subscribe(client, obj, MiD, granted_qos):
        global waiting, mid
        mid = MiD
        MySyslog.log(modulename,'DEBUG','mid: ' + str(mid) + ",qos:" + str(granted_qos))
    
    def on_log(client, obj, level, string):
        global PingTimeout, Conf, ErrorCnt
        if string.find('PINGREQ') >= 0:
            if not PingTimeout:
                PingTimeout = int(time())
            elif int(time())-PingTimeout > 10*60: # should receive pong in 10 minutes
                MySyslog.log(modulename,'ATTENT','Ping/pong timeout exceeded.\n')
                if ('fd' in Conf.keys()) and (Conf['fd'] != None):
                    Conf['fd'].disconnect()
                    waiting = False
                    Conf['registrated'] = False
                    del Conf['fd']
                    ErrorCnt += 1
                    PingTimeout = 0
        elif string.find('PINGRESP') >= 0:
            if int(time())-PingTimeout != 0:
                MySyslog.log(modulename,'DEBUG','Log: ping/pong time: %d secs\n' % (int(time())-PingTimeout))
            PingTimeout = 0
        else:
            MySyslog.log(modulename,'DEBUG','Log: %s...\n' % string[:17])

    def on_disconnect(client, obj, MiD):
        global waiting, mid, Conf
        waiting = False
        if 'fd' in Conf.keys():
            Conf['fd'] = None
        mid = MiD
        MySyslog.log(modulename,'DEBUG','Disconnect mid: ' + str(mid))
        raise IOError("MQTTsub: disconnected")

    if ('file' in Conf.keys()) and Conf['file']:
        return ReadFromFile(Conf['file'])
    try:
        if (not 'fd' in Conf.keys()) or (Conf['fd'] == None):
            Conf['fd']  = mqtt.Client(Conf['prefix']+str(os.getpid()))
            Conf['fd'].on_connect = on_connect
            Conf['fd'].on_disconnect = on_disconnect
            if ('user' in Conf.keys()) and Conf['user'] and ('password' in Conf.keys()) and Conf['password']:
                Conf['fd'].username_pw_set(username=Conf['user'],password=Conf['password'])
            #Conf['fd'].connect(Conf['hostname'], port=Conf['port'], keepalive=60)
            Conf['fd'].connect(Conf['hostname'], Conf['port'])
            Conf['fd'].on_subscribe = on_subscribe
            Conf['fd'].on_message = on_message
            Conf['fd'].loop_start()   # start thread
            Conf['fd'].subscribe(topic, qos=Conf['qos'])

        timeout = time() + Conf['timeout']
        waiting = True
        while waiting:
            if time() > timeout:
                break
            if len(telegrams):
                waiting = False
                break
            sleep(1)       # maybe it should depend on timeout
        # Conf['fd'].disconnect()
        # Conf['fd'].loop_stop()
    except:
        MySyslog.log(modulename,'ERROR','Failure type: %s; value: %s. MQTT broker aborted.\n' % (sys.exc_info()[0],sys.exc_info()[1]) )
        Conf['output'] = False
        del Conf['fd']
        raise IOError("%s" % str(mid))
        return telegram
    if waiting:
        MySyslog.log(modulename,'ATTENT','Sending telegram to broker')
        raise IOError("%s" % str(mid))
        return telegram
    MySyslog.log(modulename,'DEBUG','Received telegram from broker, waiting = %s, message id: %s' % (str(waiting),str(mid)) )
    if len(telegrams):
        return telegrams.pop(0)
    return telegram

# mqttc = mosquitto.Mosquitto()
# # Assign event callbacks
# mqttc.on_message = on_message
# mqttc.on_connect = on_connect
# mqttc.on_publish = on_publish
# mqttc.on_subscribe = on_subscribe
# 
# Uncomment to enable debug messages
#mqttc.on_log = on_log

# conversion nomenclature from TTN names to MySQL DB column names
name_table = {
    "SDS011": { "type": "dust", "pm2.5": "pm25", 'pm25': 'pm25', "pm10": "pm10", "units": "ug/m3" },
    "SHINEY": { "type": "dust", "pm2.5": "pm25", 'pm25': 'pm25', "pm10": "pm10", "units": "pcs/qf", },
    "Dylos": { "type": "dust", "pm2.5": "pm_25", 'pm25': 'pm_25', "pm10": "pm_10", "units": "pcs/0.01qf", },
    "PMS7003": { "type": "dust", "pm2.5": "pm25_atm", 'pm25': 'pm25_atm',"pm10": "pm10_atm", "pm1": "pm1_atm", "units": "ug/m3", },
    "DHT22": { "type": "meteo", "temperature": "temp", "temp": "temp", "humidity": "rv", "hum": "rv" },
    "BME280": { "type": "meteo", "temperature": "temp", "temp": "temp", "humidity": "rv", "hum": "rv", "pressure": "luchtdruk", "pres" : "luchtdruk" },
    "other": { "type": "any", "temperature": "temp", "temp": "temp", "humidity": "rv", "hum": "rv", "pressure": "luchtdruk", "pres" : "luchtdruk", "pm2.5": "pm25", "pm10": "pm10", "pm1": "pm1", "units": "pcs/qf", },
}
    
last_records = {}       # remember last record seen so far

# sensor module name is received via TTN record field 'type'
def convert2MySense( data, dust = "SDS011", meteo = "DHT22" ):
    global Conf

    ident = { 'project': 'VW2017', 'fields': ['time', ], 'types': ['time'], 'units': ['s',] }
    ident['description'] = 'MQTT AppID=' + data['topic'][0] + ' MQTT DeviceID=' + data['topic'][2]
    values = { 'time': int(time()) }
    # make sure we use nomenclature of MySQL DB
    meteo_units = { "temp": 'C', "humidity": '%', "pressure": 'hpa' }
    record = {}
    for item in ['counter','payload_raw']:
        if item in data['payload'].keys():
            record[item] = data['payload'][item]
    if "payload_fields" in data['payload'].keys():
        if 'type' in data['payload']['payload_fields'].keys():
            if data['payload']['payload_fields']['type'] in name_table.keys():
                dust = data['payload']['payload_fields']['type']
            else:
                MySyslog.log(modulename,'ERROR','Unknown dust sensor type: %s' % data['payload']['payload_fields']['type'])
        for item in data['payload']['payload_fields'].keys():
            if item == 'type':
               continue
            name = item.lower()
            if name in name_table[dust].keys():
                name = name_table[dust][name]
            elif name in name_table[meteo].keys():
                name = name_table[meteo][name]
            else:
                MySyslog.log(modulename,'ATTENT','Unknown sensor item: %s' % item)
                continue
            values[name] = data['payload']['payload_fields'][item]

    # default sensors SDS011 and DHT22
    for sensor in Conf['dust']:
        if sensor in name_table[dust].keys():
            ident['fields'].append(name_table[dust][sensor])
            ident['types'].append(dust)
            ident['units'].append(name_table[dust]['units'])
    for sensor in Conf['meteo']:
        if sensor in name_table[meteo].keys():
            ident['fields'].append(name_table[meteo][sensor])
            ident['types'].append(meteo)
            ident['units'].append(meteo_units[sensor])

    # provide the device with a static serial number
    ident['serial'] = hex(hash(data['topic'][0] + '/' + data['topic'][2])&0xFFFFFFFFFF)[2:]
    # try to get geolocation
    geolocation = []
    if "metadata" in data['payload'].keys():
        for item in ['latitude','longitude','altitude']:
            if item in data['payload']['metadata'].keys():
                geolocation.append(str(data['payload']["metadata"][item]))
            else:
                geolocation.append('?')
        geolocation = ','.join(geolocation)
        for item in data['payload']['metadata'].keys():
            if item in ['time',]:
                if item == 'time':      # convert iso timestamp to UNIX timestamp
                    values['time'] = int(dp.parse(data['payload']['metadata']['time']).strftime("%s"))
                    record['time'] = values['time']
                else:
                    values[item] = data['payload']['metadata'][item]
    if (len(geolocation) <= 10):
        geolocation = "?"
    ident['geolocation'] = geolocation    # might note we did ident once
    record['geolocation'] = geolocation

    # maintain info last seen of this device
    if ident['serial'] in last_records.keys():
        if 'geolocation' in last_records[ident['serial']].keys():
            if last_records[ident['serial']]['geolocation'] != ident['geolocation']:
                # sensorkit changed location
                values['geolocation'] = ident['geolocation']
                # keep first location in ident
                ident['geolocation'] = last_records[ident['serial']]['geolocation']
    else:
        record['geolocation'] = ident['geolocation']
        last_records[ident['serial']] = record

    ident = updateIdent( data['topic'][0], data['topic'][2], ident)
    if len(values) < 2: return {}
    return { 'ident': ident, 'data': values }

def getdata():
    global Conf, ErrorCnt
    if ErrorCnt:
        if ErrorCnt > 20:
            Conf['registrated'] = None
            if ('fd' in Conf.keys()) and (Conf['fd'] != None):
                try:
                    Conf['fd'].disconnect()
                    Conf['fd'] = None
                except:
                    pass
            sleep((ErrorCnt-20)*60)
        else:
            sleep(ErrorCnt)
    
    # input from file or from MQTT LoRa TTN broker
    if (not 'file' in Conf.keys()) or (not Conf['file']):
        if (not 'registrated' in Conf.keys()) or (Conf['registrated'] == None):
            if 'registrated' in Conf.keys():
                MySyslog.log(modulename,'ATTENT','Try to reconnect to broker.')
            if (not 'AppId' in Conf.keys()) or (not len(Conf['AppId'])):
                Conf['AppId'] = '+'
            if (not 'DevAddr' in Conf.keys()) or (not len(Conf['DevAddr'])):
                Conf['DevAddr'] = '+'
            if (not 'topic' in Conf.keys()) or (Conf['topic'] == None):
                Conf['topic'] = 'devices'
            for key in ['user','password','hostname']:
                if (not key in Conf.keys()) or (Conf[key] == None):
                    Conf['input'] = False
                    MySyslog.log(modulename,'FATAL','Missing login %s credentials.' % key)
            Conf['registrated'] = True

    try:
        msg = PubOrSub("%s/%s/%s/up" % (Conf['AppId'],Conf['topic'],Conf['DevAddr']), None)
        if msg == None:
            ErrorCnt += 1
            return {}
        ErrorCnt = 0
        msg['topic'] = msg['topic'].split('/')
        msg['payload'] = json.loads(msg['payload'])
    except IOError as e:
        if ErrorCnt > 40:
            MySyslog.log(modulename,'FATAL','Subscription failed Mid: %s. Aborted.' % e)
        ErrorCnt += 1
        MySyslog.log(modulename,'WARNING','Subscription is failing Mid: %s. Slowing down.' % e)
    if (len(msg['topic']) < 3) or (msg['topic'][1] != Conf['topic']) or (not type(msg['payload']) is dict) or (not 'dev_id' in msg['payload'].keys()):
        MySyslog.log(modulename,'ERROR','Received an unknow record %s' % str(msg))
        sleep(0.1)
        return getdata()
    msg['AppId'] = msg['topic'][0]
    msg['DevAddr'] = msg['topic'][2]
    # check the pay load
    if not type(msg['payload']) is dict:
        sleep(0.1)
        return getdata()
    # TO DO: check DevAddr to api key (mqtt broker checks user with AppId/DevAddr)
    # copy items we need
    return convert2MySense(msg)

# MAIN part of Broker for VW 2017

if __name__ == '__main__':
    # 'NOTSET','DEBUG','INFO','ATTENT','WARNING','ERROR','CRITICAL','FATAL'
    MyLogger.Conf['level'] = 10     # log from and above 10 * index nr
    MyLogger.Conf['file'] = '/dev/stderr'
    error_cnt = 0
    OutputChannels = [
        {   'name': 'MySQL DB', 'script': 'DB-upload-MySQL', 'module': None,
            'Conf': {
                'output': True,
                'hostname': 'localhost', 'database': 'luchtmetingen',
                'user': 'IoS', 'password': 'acacadabra',
            }
        },
        ]
    try:
        for indx in range(0,len(OutputChannels)):
            OutputChannels[indx]['module'] = __import__(OutputChannels[indx]['script'])
            for item in OutputChannels[indx]['Conf'].keys():
                OutputChannels[indx]['module'].Conf[item] = OutputChannels[indx]['Conf'][item]
                OutputChannels[indx]['errors'] = 0
            MySyslog.log(modulename,'INFO','Enabled output channel %s' % OutputChannels[indx]['name'])
    except ImportError as e:
        MySyslog.log(modulename,'ERROR','One of the import modules not found: %s' % e)
    net = { 'module': True, 'connected': True }

# devices
    # configure MySQL luchtmetingen DB access
    while 1:
        if error_cnt > 20:
            MySyslog.log(modulename,'FATAL','To many input errors. Stopped broker')
            exit(1)
        try:
            record = getdata()
        except:
            MySyslog.log(modulename,'INFO','No more input data available')
            exit(0)
        if (not dict(record)) or (len(record['data']) < 2):
            MySyslog.log(modulename,'ATTENT','Data failure from LoRaWan data concentrator')
            error_cnt += 1
            continue
        cnt = 0
        if 'description' in record['ident'].keys():
            MySyslog.log(modulename,'INFO','%s Got data from %s' % (datetime.datetime.fromtimestamp(record['data']['time']).strftime("%Y-%m-%d %H:%M"),record['ident']['description']))
        else:
            MySyslog.log(modulename,'INFO','%s Got data (no description)' % datetime.datetime.fromtimestamp(record['data']['time']).strftime("%Y-%m-%d %H:%M"))
        for indx in range(0,len(OutputChannels)):
            if OutputChannels[indx]['module'] and OutputChannels[indx]['Conf']['output']:
                try:
                    OutputChannels[indx]['module'].publish(
                        ident = record['ident'],
                        data = record['data'],
                        internet = net
                    )
                    OutputChannels[indx]['errors'] = 0
                    cnt += 1
                except:
                    MySyslog.log(modulename,'ERROR','sending record to %s' % OutputChannels[indx]['name'])
                    OutputChannels[indx]['errors'] += 1
            if OutputChannels[indx]['errors'] > 20: OutputChannels[indx]['module']['Conf']['output'] = False
        if not cnt:
            MySyslog.log(modulename,'FATAL','No output channel available. Exiting')
            exit(1)