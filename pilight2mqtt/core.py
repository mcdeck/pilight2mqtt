#!/usr/bin/env python
# -*- coding: utf-8 -*-

"""
core module of pilight2mqtt
"""

from __future__ import print_function

import socket
import sys
import re
import json
import signal
import logging

import paho.mqtt.client as mqtt

from pilight2mqtt.discover import discover

__all__ = ['Pilight2MQTT', 'PilightServer']

DISCOVER_SCHEMA = "urn:schemas-upnp-org:service:pilight:1"


class ConnectionLostException(Exception):
    """Connection lost exception"""
    pass


class Loggable(object):  # pylint: disable=too-few-public-methods
    """base class for objects that need logging"""

    @property
    def log(self):
        """log message to a logger named like the class"""
        return logging.getLogger(self.__class__.__name__)


class PilightServer(Loggable):
    """class to interact with pilight"""

    @classmethod
    def discover(cls):
        """discover pilight servers in the network"""
        log = logging.getLogger('PilightAutoDiscover')

        log.debug('trying to discover servers')
        responses = discover(DISCOVER_SCHEMA)
        if len(responses) == 0:
            log.error('failed to locate any servers - terminating')
            sys.exit(1)
        locationsrc = re.search('Location:([0-9.]+):([0-9.]+)',
                                str(responses[0]),
                                re.IGNORECASE)
        if locationsrc:
            location = locationsrc.group(1)
            port = locationsrc.group(2)
        else:
            log.error("Whoops, could not find any servers")
            sys.exit(1)
        log.info('Found server at %s:%d', location, int(port))
        return PilightServer(location, int(port))

    def __init__(self, address, port):
        """initialize"""
        self.log.debug('__init__(%s, %s)', address, port)
        self._address = address
        self._port = port
        self._socket = None
        self._should_terminate = True
        self._event_handler = None

    def _read(self):
        """read data from socket"""
        self.log.debug('read')
        text = b""
        while not self._should_terminate:
            try:
                line = self._socket.recv(1024)
            except socket.timeout:
                continue
            except Exception as ex:  # pylint: disable=broad-except
                self.log.debug(ex)
            text += line
            if b"\n\n" in line[-2:]:
                text = text[:-2]
                break
        return text

    def send_check_success(self, msg_dct):
        """send message and check that it was successfull"""
        self.log.debug('_send_check_success')
        response = self.send_json(msg_dct)
        if response.get('status', '') == 'success':
            return True
        return False

    def send_json(self, msg_dct):
        """send json data and read response, which is also json"""
        self.log.debug('_send_json')
        msg = bytes(json.dumps(msg_dct)+'\n', 'utf-8')
        response = self.send_raw(msg)
        if self._should_terminate:
            return {}
        return json.loads(response.decode("utf-8"))

    def send_raw(self, msg):
        """send and read raw data"""
        self.log.debug('_send_raw')
        self._socket.send(msg)
        response = self._read()
        return response

    def _open_socket(self):
        """open a socket to pilight"""
        self.log.debug('open socket')
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._socket.settimeout(1)
        self._socket.connect((self._address, int(self._port)))
        self._should_terminate = False

    def connect(self, cb_recv=None):
        """initialize connection progress.
           registers handlers as well.
        """
        self.log.info('connect')
        if cb_recv:
            self._event_handler = cb_recv
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

    def reconnect(self):
        """try to reconnect if the connection got lost"""
        try:
            connected = False
            while not self._should_terminate and not connected:
                connected = self.connect()
            return connected
        except Exception:  # pylint: disable=broad-except
            pass
        return False

    def disconnect(self):
        """disconnect from pilight"""
        self.log.info('disconnect')
        self._should_terminate = True
        if self._socket:
            self._socket.close()
            self._socket = None

    def process_events(self, callback):
        """process incoming events from pilight"""
        self.log.info('process_events')
        while not self._should_terminate:
            response = self._read()
            if not self._should_terminate:
                self.log.debug('call callback')
                callback(response)

    def terminate(self):
        """indicate that the system should shut down"""
        self.log.info('terminate')
        self._should_terminate = True

    def heartbeat(self):
        """send and read heart beat to/from pilight"""
        response = self.send_raw(b'HEART')
        if response == b'BEAT':
            return True
        return False

    def set_device_state(self, device, state):
        """update the state of a device in pilight"""
        self.log.info('set_device_state: "%s" to "%s"', device, state)
        msg = {
            'action': 'control',
            'code': {
                'device': device,
                'state': state
            }
        }
        return self.send_check_success(msg)


class Pilight2MQTT(Loggable):
    """translate between pilight events and mqtt messages"""

    def __init__(self, server, mqtt_host,
                 mqtt_port=1883, mqtt_topic='PILIGHT'):
        """initialize"""
        self.log.debug('__init__')
        self._mqtt_host = mqtt_host
        self._mqtt_port = mqtt_port
        self._mqtt_topic = mqtt_topic
        self._server = server

        def on_connect(client, userdata, flags, result_code):
            # pylint: disable=missing-docstring
            return self._on_connect(client, userdata, flags, result_code)

        def on_message(client, userdata, msg):
            # pylint: disable=missing-docstring
            return self._on_message(client, userdata, msg)

        self._mqtt_client = mqtt.Client()
        self._mqtt_client.on_connect = on_connect
        self._mqtt_client.on_message = on_message

    def _on_connect(self, client, userdata, flags, result_code):
        """execute setup of mqtt, i.e. subscribe to a channel"""
        self.log.debug("Connected with result code "+str(result_code))
        # Subscribing in on_connect() means that if we lose the connection and
        # reconnect then subscriptions will be renewed.
        self.log.info('MQTT Subscribe %s', self._mqtt_topic)
        client.subscribe("%s/#" % self._mqtt_topic)

    def _on_message(self, client, userdata, msg):
        """process messages received from MQTT"""
        self.log.debug(msg.topic+" "+str(msg.payload))
        match = re.search('%s/set/(.*?)/STATE' % self._mqtt_topic, msg.topic)
        if match:
            device = match.group(1)
            state = msg.payload
            self._server.set_device_state(device, state.decode('utf-8'))

    def _send_mqtt_msg(self, device, topic, payload):
        self.log.info('Update for device "%s" on topic "%s", new value "%s"', device, payload, topic)  # flake8: NOQA pylint: disable=line-too-long
        (result, mid) = self._mqtt_client.publish(topic,
                                                  payload=payload,
                                                  qos=0,
                                                  retain=False)
        assert result == mqtt.MQTT_ERR_SUCCESS, "Failed to send message (%s)" % str(result)  # flake8: NOQA pylint: disable=line-too-long
        self.log.debug('Message send with id %d', mid)

    def _mktopic(self, device, reading):
        return '%s/status/%s/%s' % (self._mqtt_topic, device, reading)

    def _handle_event(self, evt):
        """event handling for message from pilight"""
        self.log.debug(evt)
        try:
            evt_dct = json.loads(evt.decode('utf-8'))
            if evt_dct.get('origin', '') == 'update':
                evt_type = evt_dct.get('type', None)
                if evt_type == 1: # switch
                    for device in evt_dct.get('devices', []):
                        self._send_mqtt_msg(device,
                                            self._mktopic(device, 'STATE'),
                                            evt_dct['values']['state'])
                elif evt_type == 3:
                    for device in evt_dct.get('devices', []):
                        self._send_mqtt_msg(device,
                                            self._mktopic(device, 'HUMIDITY'),
                                            evt_dct['values']['humidity'])
                        self._send_mqtt_msg(device,
                                            self._mktopic(device, 'TEMPERATURE'),
                                            evt_dct['values']['temperature'])
                else:
                    raise RuntimeError('Unsupported event type %d' % evt_type)
        except Exception as ex:  # pylint: disable=broad-except
            self.log.error('%s: %s', ex.__class__.__name__, ex)

    def run(self):
        """main run method"""
        self.log.debug('run')

        def stop_server(signum, frame):  # pylint: disable=missing-docstring
            self.log.debug("SIGINT")
            self._server.terminate()
        signal.signal(signal.SIGINT, stop_server)

        self.log.info('MQTT Connect %s:%d',
                      self._mqtt_host, self._mqtt_port)
        try:
            self._mqtt_client.connect(self._mqtt_host, self._mqtt_port, 60)
        except Exception as ex:  # pylint: disable=broad-except
            self.log.error('Failed to connect to MQTT server: %s', str(ex))
            return 1
        self._mqtt_client.loop_start()

        suc = self._server.connect()
        if not suc:
            self.log.error('Could not connect to server')
            return 1

        assert self._server.heartbeat()

        def callback(event):  # pylint: disable=missing-docstring
            self._handle_event(event)

        self._server.process_events(callback)
        self._server.disconnect()

        self.log.info('disconnect MQTT')
        self._mqtt_client.loop_stop(force=False)
        self._mqtt_client.disconnect()

        return 0
