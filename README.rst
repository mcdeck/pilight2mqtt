pilight2mqtt
============

Proxy messages between pilight and mqtt


Tips & Tricks
-------------
**Q**: Autodiscovery fails, what is the port to use?

**A**: You can specify the port pilight listens on in the pilight configuration 
under settings, port. https://manual.pilight.org/en/configuration-settings#pf2

Remember to first stop pilgith and only modify the settings afterwards. At least
for me pilight will overwrite the configuration with its current values when shutting
down.


Build Status
------------
.. image:: https://travis-ci.org/mcdeck/pilight2mqtt.svg?branch=master
    :target: https://travis-ci.org/mcdeck/pilight2mqtt

Requirements
------------
* Python 3.4+
