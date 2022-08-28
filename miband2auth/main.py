import logging
from .authwindow import auth_window
from .authsession import auth_session
from .authsession import DEF_AUTH_POLICY
from dbus.mainloop import glib
from queue import Queue
import dbus

from . import authsession


def isDeviceSupported(bus, opath):
    proxy = bus.get_object('org.bluez', opath)
    interface = dbus.Interface(proxy, 'org.freedesktop.DBus.Properties')
    dev_name = interface.Get('org.bluez.Device1', 'Name')
    return dev_name == 'MI Band 2'

def main():
    bus = dbus.SystemBus(mainloop=glib.DBusGMainLoop())

    q = Queue()

    def on_auth_complete(dev_path, _):
        q.put(dev_path)

    def session_provider(dev_path):
        if isDeviceSupported(bus, dev_path):
            return auth_session(bus, dev_path, on_auth_complete, DEF_AUTH_POLICY)
        print(f"{dev_path}: skipping unrecognized device")

    logging.getLogger(authsession.__name__).setLevel(logging.DEBUG)

    print("Band auth agent has started...")
    auth_w = auth_window(bus)
    auth_w.start()
    auth_w.register_unknown_dev_handler(session_provider)

    timeout = 50
    dev_found = True

    while dev_found:
        try:
            q.get(timeout=timeout)
        except:
            dev_found = False
            print(f'no devices found. Timed out waiting for new connections for the last {timeout} sec')
