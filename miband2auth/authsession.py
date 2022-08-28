from dataclasses import dataclass
import enum
import pyaes
import logging
import dbus


logging.basicConfig()
logger = logging.getLogger(__name__)

class key_reset_option(enum.Enum):
    YES = 1
    ON_KEY_MISMATCH = 2
    NO = 3

@dataclass
class auth_policy:
    key: bytes
    reset_option: key_reset_option

DEF_AUTH_POLICY = auth_policy(
    b'\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x01',
    key_reset_option.ON_KEY_MISMATCH
)

AUTH_CHAR_PATH_TEMPLATE = '{dev_path}/service0052/char0053'

class auth_status(enum.Enum):
    OK = 1
    TIMED_OUT = 2
    NEW_KEY_ABORTED = 3
    KEY_MISMATCH = 4

class auth_session:

    def __init__(self, bus, dev_path, complete_cb, auth_policy) -> None:
        self.auth_policy = auth_policy

        self.dev_path = dev_path
        self.complete_cb = complete_cb

        def on_complete_teardown(it, status):
            self.stop()
            logger.debug(f"{self.dev_path}: {status}")
            complete_cb(it, status)
        self.complete_cb = on_complete_teardown

        self.auth_char_path = AUTH_CHAR_PATH_TEMPLATE.format(dev_path=self.dev_path)
        self.proxy = bus.get_object('org.bluez', self.auth_char_path)
        self.auth_char = dbus.Interface(self.proxy, 'org.bluez.GattCharacteristic1')
        
        self.handlers = {
            b'\x10\x01\x01': self._on_key_accepted,
            b'\x10\x02\x01': self._on_rand_msg_received,
            b'\x10\x03\x01': self._on_auth_ok,
            b'\x10\x01\x02': self._on_new_key_aborted,
            b'\x10\x03\x04': self._on_key_mismatch
        }

    def _handle_auth_notification(self, iface, props, _):
        if 'Value' not in props:
            return
        code = bytes(props['Value'][:3])
        val = props['Value'][3:]

        handler = self.handlers.get(code, None)

        if handler is None:
            logger.debug(f'unknown notification: code: {code}, msg: {val}')
            return

        handler(val)

    def start(self):
        logger.info(f"{self.dev_path}: session started")

        self.auth_signal = self.proxy.connect_to_signal("PropertiesChanged", self._handle_auth_notification)
        self.auth_char.StartNotify()

        if self.auth_policy.reset_option == key_reset_option.YES:
            self._send_key()
        else:
            self._req_secret()

    def stop(self):
        logger.info(f"{self.dev_path}: session finished")
        self.auth_char.StopNotify()
        self.auth_signal.remove()

    def _req_secret(self):
        logger.debug(f"-> {self.dev_path}: sending a random msg request")
        self.auth_char.WriteValue([2,0], {})

    def _send_key(self):
        logger.debug(f"-> {self.dev_path}: sending a new key to a peer")
        self.auth_char.WriteValue([1,0] + list(self.auth_policy.key), {})

    def _send_enc_msg(self, msg):
        logger.debug(f"-> {self.dev_path}: sending an encrypted random msg")
        aes = pyaes.AESModeOfOperationECB(self.auth_policy.key)
        msg = list(aes.encrypt(bytes(msg)))
        self.auth_char.WriteValue([3,0] + msg, {})

    def _on_key_accepted(self, msg):
        logger.debug(f"<- {self.dev_path}: a new key is accepted ")
        self._req_secret()

    def _on_rand_msg_received(self, msg):
        logger.debug(f"<- {self.dev_path}: random msg received")
        self._send_enc_msg(msg)

    def _on_auth_ok(self, msg):
        logger.debug(f"<- {self.dev_path}: encrypted msg confirmed")
        self.complete_cb(self.dev_path, auth_status.OK)

    def _on_new_key_aborted(self, msg):
        logger.debug(f"<- {self.dev_path}: new key confirmation timed out")
        self.complete_cb(self.dev_path, auth_status.NEW_KEY_ABORTED)

    def _on_key_mismatch(self, msg):
        logger.warning(f"<- {self.dev_path}: key mismatch")
        if self.auth_policy.reset_option == key_reset_option.ON_KEY_MISMATCH:
            logger.info(f"{self.dev_path}: trying to reset a key")
            self._send_key()
        else:
            self.complete_cb(self.dev_path, auth_status.KEY_MISMATCH)
