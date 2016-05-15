#!/usr/bin/env python
# -*- coding: utf-8 -*-
import socket
import re
import json
import signal
import logging

import paho.mqtt.client as mqtt

from pilight2mqtt.discover import discover

__all__ = ['Pilight2MQTT', 'PilightServer']


class Loggable(object):
  @property
  def log(self):
    return logging.getLogger(self.__class__.__name__)
    
    
class PilightServer(Loggable):
    def __init__(self, address, port):
        self.log.debug('__init__(%s, %s)' % (address, port))
        self._address = address
        self._port = port
        self._socket = None
        self._should_terminate = True
                
    def _read(self):
        self.log.debug('read')
        text = b"";
        while not self._should_terminate:
            try:
                line = self._socket.recv(1024)
            except Exception as ex:
                self.log.debug(ex)
                continue
            text += line
            if b"\n\n" in line[-2:]:
                text = text[:-2];
                break
        return text
        
    def send_check_success(self, msg_dct): 
        self.log.debug('_send_check_success')
        response = self.send_json(msg_dct)
        if response.get('status', '') == 'success':
            return True
        return False
        
    def send_json(self, msg_dct):
        self.log.debug('_send_json')
        msg = bytes(json.dumps(msg_dct)+'\n', 'utf-8')
        response = self.send_raw(msg)
        if self._should_terminate:
            return {}
        return json.loads(response.decode("utf-8"))
        
    def send_raw(self, msg): 
        self.log.debug('_send_raw')
        self._socket.send(msg)
        response = self._read()
        return response
        
    def _open_socket(self):
        self.log.debug('open socket')
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(1)
        self._socket.connect((self._address, int(self._port)))
        self._should_terminate = False
        
    def connect(self, cb_recv=None):
        self.log.info('connect')
        self._open_socket()
        suc = self.send_check_success({
            'action': 'identify',
            'options': {
                'receiver': 1,
                'core': 0,
                'config': 1,
                'forward': 1                
            },
            'uuid': '0000-d0-63-00-000000',
            'media': 'all'
        })
        return suc

    def disconnect(self):
        self.log.info('disconnect')
        self._should_terminate = True
        if self._socket:
            self._socket.close()
            self._socket = None
            
    def process_events(self, callback):
        self.log.info('process_events')
        while not self._should_terminate:
            response = self._read()
            if not self._should_terminate:
                self.log.debug('call callback')
                callback(response)
                
    def terminate(self):
        self.log.info('terminate')
        self._should_terminate = True
        
    def hearbeat(self):
        response = self.send_raw(b'HEART')
        if response == b'BEAT':
            return True
        return False
        
    def set_device_state(self, device, state):
        self.log.info('set_device_state: "%s" to "%s"' % (device, state))
        msg = {
            'action': 'control',
            'code': {
                'device': device,
                'state': state
            }
        }
        return self.send_check_success(msg)
        
        
class Pilight2MQTT(Loggable):
    def __init__(self, mqtt_host, mqtt_port=1883, mqtt_topic='PILIGHT', server=None):
        self.log.debug('__init__')
        self._mqtt_host = mqtt_host
        self._mqtt_port = mqtt_port
        self._mqtt_topic = mqtt_topic
        
        self._server = server
        if not self._server:
            self.log.debug('trying to discover servers')
            responses = discover("urn:schemas-upnp-org:service:pilight:1")
            assert len(responses) > 0
            locationsrc = re.search('Location:([0-9.]+):([0-9.]+)', str(responses[0]), re.IGNORECASE)
            if locationsrc:
                location = locationsrc.group(1)
                port = locationsrc.group(2)  
            else: 
                self.log.error("Whoops, could not find any servers")
                sys.exit(1)
            self.log.info('Found server at %s:%d' % (location, int(port)))
            self._server = PilightServer(location, int(port))
            
        def on_connect(client, userdata, flags, rc):
            return self._on_connect(client, userdata, flags, rc)
        def on_message(client, userdata, msg):
            return self._on_message(client, userdata, msg)
        self._mqtt_client = mqtt.Client()
        self._mqtt_client.on_connect = on_connect
        self._mqtt_client.on_message = on_message

    def _on_connect(self, client, userdata, flags, rc):
        self.log.debug("Connected with result code "+str(rc))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        self.log.info('MQTT Subscribe %s' % self._mqtt_topic)
        client.subscribe("%s/#" % self._mqtt_topic)

    def _on_message(self, client, userdata, msg):
        self.log.debug(msg.topic+" "+str(msg.payload))     
        m = re.search('%s/(.*?)/state' % self._mqtt_topic, msg.topic)
        if m:
            device = m.group(1)
            state = msg.payload           
            self._server.set_device_state(device, state.decode('utf-8'))
        
    def run(self):
        self.log.debug('run')
        def stop_server(signum, frame):
            self.log.debug("SIGINT")
            self._server.terminate()
        signal.signal(signal.SIGINT, stop_server)
        
        self.log.info('MQTT Connect %s:%d' % (self._mqtt_host, self._mqtt_port))
        self._mqtt_client.connect(self._mqtt_host, self._mqtt_port, 60)
        self._mqtt_client.loop_start()

        suc = self._server.connect()
        if not suc:
            self.log.warn('Could not connect to server')
            return
        assert self._server.hearbeat()
        def cb(x):
            self.log.debug(x)
        self._server.process_events(cb)
        self._server.disconnect()
    
        self.log.info('disconnect MQTT')
        self._mqtt_client.loop_stop(force=False)
        self._mqtt_client.disconnect()
        