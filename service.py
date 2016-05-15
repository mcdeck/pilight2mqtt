#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
from pilight2mqtt import Pilight2MQTT

if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    Pilight2MQTT().run()
    