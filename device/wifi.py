"""WiFi connection. Credentials live in config.json on the device, never in this file."""
import network
import time


def connect(ssid, password, timeout_s=30):
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    if wlan.isconnected():
        return wlan.ifconfig()[0]
    wlan.connect(ssid, password)
    t = time.ticks_ms()
    while not wlan.isconnected():
        if time.ticks_diff(time.ticks_ms(), t) > timeout_s * 1000:
            raise RuntimeError("wifi timeout for %r" % ssid)
        time.sleep_ms(250)
    return wlan.ifconfig()[0]


def scan():
    wlan = network.WLAN(network.STA_IF)
    wlan.active(True)
    return sorted(((net[3], net[0].decode()) for net in wlan.scan()), reverse=True)
