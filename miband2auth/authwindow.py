import logging
import threading
from gi.repository import GLib
from .authsession import auth_status

logging.basicConfig()
logger = logging.getLogger(__name__)

def nop_session_provider(dev_path):
    pass

class auth_window(threading.Thread):
    def __init__(self, bus) -> None:
        super().__init__(daemon=True)
        self.bus = bus
        self.mainloop = GLib.MainLoop()
        self.pending_sessions = {}
        self.def_provider = nop_session_provider
    
    def run(self):
        logger.info('Started observing for dev connections')
        self.bus.add_signal_receiver(self.handle_dev_connected, signal_name = "PropertiesChanged", bus_name="org.bluez", path_keyword="opath")
        self.mainloop.run()
    
    def stop(self):
        self.mainloop.quit()
        self.bus.remove_signal_receiver(self.handle_dev_connected, signal_name = "PropertiesChanged", bus_name="org.bluez")

    def register_session(self, dev_path, sess):
        self.pending_sessions[dev_path] = sess

    def register_unknown_dev_handler(self, provider):
        self.def_provider = provider
    
    def remove_unknown_dev_handler(self):
        self.def_provider = nop_session_provider

    def _get_dev_session(self, dev_path):
        sess = self.pending_sessions.get(dev_path, None)

        if sess is None:
            sess = self.def_provider(dev_path)
            if sess is not None:
                self.pending_sessions[dev_path] = sess
        
        return sess

    def on_opened(self, dev_path):
        sess = self._get_dev_session(dev_path)
        if sess is None:
            return

        logger.info(f'opened for {dev_path}')
        orig_cb = sess.complete_cb

        def mark_complete(path, status):
            del self.pending_sessions[path]
            orig_cb(path,status)
        
        sess.complete_cb = mark_complete
        sess.start()


    def on_closed(self, dev_path):
        sess = self.pending_sessions.get(dev_path,None)
        if sess is None:
            return
        logger.info(f'closed for {dev_path}')
        sess.complete_cb(dev_path, auth_status.TIMED_OUT)

    def handle_dev_connected(self, iface, props, _, opath):
        is_connected = props.get('ServicesResolved', None)
        if is_connected == None:
            return

        if is_connected:
            self.on_opened(opath)
        else:
            self.on_closed(opath)
            