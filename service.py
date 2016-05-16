#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from pilight2mqtt import PilightServer, Pilight2MQTT

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    server = PilightServer.discover()
    Pilight2MQTT(server, 'spock').run()
    