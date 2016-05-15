#!/usr/bin/env python
# -*- coding: utf-8 -*-
import socket
import re
import json
import signal
import logging

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
        
    def __del__(self):
        self.log.debug('__del__')
        self.disconnect()
        
    def _read(self):
        self.log.debug('read')
        text = b"";
        while not self._should_terminate:
            try:
                line = self._socket.recv(1024)
            except:
                continue
            text += line
            if b"\n\n" in line[-2:]:
                text = text[:-2];
                break
        if self._should_terminate:
            return {}
        return json.loads(str(text))
        
    def _send(self, msg_dct): 
        self.log.debug('send')
        msg = bytes(json.dumps(msg_dct)+'\n', 'utf-8')
        self._socket.send(msg)
        response = self._read()
        if 'status' in response:
            if reponse['status'] == 'success':
                return True
        return False
        
    def _open_socket(self):
        self.log.debug('open socket')
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(1)
        self._socket.connect((self._address, int(self._port)))
        self._should_terminate = False
        
    def connect(self, cb_recv=None):
        self.log.debug('connect')
        self._open_socket()
        suc = self._send({
            'action': 'identfy',
            'options': {
                'receiver': 1
            }
        })
        return suc

    def disconnect(self):
        self.log.debug('disconnect')
        self._should_terminate = True
        if self._socket:
            self._socket.close()
            self._socket = None
            
    def process_events(self, cb):
        self.log.debug('process_events')
        while not self._should_terminate:
            response = self._read()
            for f in iter(text.splitlines()):
                cb(json.loads(str(f)))
                
    def terminate(self):
        self.log.debug('terminate')
        self._should_terminate = True
        
    def send(self, msg):
        pass

        
class Pilight2MQTT(Loggable):
    def __init__(self, server=None):
        self.log.debug('__init__')
        self._server = server
        if not self._server:
            self.log.info('trying to discover servers')
            responses = discover("urn:schemas-upnp-org:service:pilight:1")
            assert len(responses) > 0
            locationsrc = re.search('Location:([0-9.]+):([0-9.]+)', str(responses[0]), re.IGNORECASE)
            if locationsrc:
                location = locationsrc.group(1)
                port = locationsrc.group(2)  
            else: 
                assert False
            self.log.info('Found server at %s:%d' % (location, int(port)))
            self._server = PilightServer(location, int(port))

    def run(self):
        self.log.debug('run')
        def stop_server(signum, frame):
            self.log.debug("SIGINT")
            self._server.terminate()
        signal.signal(signal.SIGINT, stop_server)
        
        suc = self._server.connect()
        if not suc:
            self.log.warn('Could not connect to server')
            return
        def cb(x):
            print(x)
        self._server.process_events(cb)
        self._diconnect()
    