from pilight2mqtt.core import PilightServer


def test_init():
    p = PilightServer('localhost', 5001)
    assert p
