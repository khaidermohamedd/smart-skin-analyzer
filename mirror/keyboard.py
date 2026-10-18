"""Lecture directe du clavier (Linux, evdev), indépendante de la fenêtre.

Sur le bureau Wayland du Raspberry Pi, la fenêtre OpenCV ne reçoit pas toujours le
clavier (focus). Ce thread lit les touches sur tous les claviers branchés.
Nécessite : sudo apt install python3-evdev, et l'utilisateur dans le groupe « input ».
"""
import threading
import time


class KeyboardListener:
    def __init__(self):
        self.pressed = set()           # noms des touches appuyées depuis la dernière lecture
        self.down_since = {}           # touche maintenue -> heure où elle a été enfoncée
        self.ok = False
        self._lock = threading.Lock()
        try:
            import evdev
        except ImportError:
            return
        self.ok = True
        for path in evdev.list_devices():
            try:
                dev = evdev.InputDevice(path)
            except OSError:
                continue
            caps = dev.capabilities().get(evdev.ecodes.EV_KEY, [])
            if evdev.ecodes.KEY_SPACE in caps:          # c'est un clavier
                threading.Thread(target=self._read, args=(dev, evdev), daemon=True).start()

    def _read(self, dev, evdev):
        try:
            for ev in dev.read_loop():
                if ev.type == evdev.ecodes.EV_KEY and ev.value in (0, 1):  # 1 = enfoncée, 0 = relâchée
                    name = evdev.ecodes.KEY.get(ev.code)
                    name = name if isinstance(name, str) else str(name)
                    with self._lock:
                        if ev.value == 1:
                            self.pressed.add(name)
                            self.down_since[name] = time.time()
                        else:
                            self.down_since.pop(name, None)
        except OSError:
            pass                                         # clavier débranché

    def held_for(self, key):
        """Depuis combien de secondes `key` est maintenue enfoncée (0 si relâchée)."""
        with self._lock:
            t = self.down_since.get(key)
        return time.time() - t if t else 0.0

    def take(self, key):
        """True si `key` (ex. "KEY_SPACE") a été appuyée depuis le dernier appel."""
        with self._lock:
            if key in self.pressed:
                self.pressed.discard(key)
                return True
        return False
