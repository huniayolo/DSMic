"""DSMic - mikrofon erősítő / torzító / minőség-csökkentő, Discordhoz.

A mikrofon jelét feldolgozza, majd egy kiválasztott kimenetre (pl. VB-CABLE virtuális
kábel) küldi. Discordban a virtuális kábel kimenetét kell bemeneti eszköznek beállítani.
"""
import collections
import json
import os
import sys
import threading
try:
    import winreg
except ImportError:  # nem Windows
    winreg = None
from pathlib import Path

import customtkinter as ctk
import numpy as np
import sounddevice as sd

if getattr(sys, "frozen", False):  # telepített exe: a Program Files nem írható -> AppData
    BASE = Path(os.environ.get("APPDATA", Path.home())) / "DSMic"
    BASE.mkdir(parents=True, exist_ok=True)
else:
    BASE = Path(__file__).parent
CONFIG = BASE / "settings.json"
BLOCK = 512

DEFAULTS = {
    "api": "",
    "input": "",
    "output": "",
    "gain_db": 0.0,
    "distortion": 0.0,
    "bits": 16,
    "rate": 48000,
    "preset": "normal",
    "presets": {},
    "lang": "hu",
    "autostart": False,
    "start_min": False,
}

# beépített presetek (azonosító -> értékek); a megjelenő név nyelvfüggő
BUILTIN_PRESETS = {
    "normal":    {"gain_db": 0.0,  "distortion": 0.0,  "bits": 16, "rate": 48000},
    "loud":      {"gain_db": 12.0, "distortion": 0.15, "bits": 16, "rate": 48000},
    "radio":     {"gain_db": 6.0,  "distortion": 0.2,  "bits": 10, "rate": 12000},
    "phone":     {"gain_db": 4.0,  "distortion": 0.1,  "bits": 8,  "rate": 8000},
    "robot":     {"gain_db": 3.0,  "distortion": 0.35, "bits": 6,  "rate": 6000},
    "megaphone": {"gain_db": 14.0, "distortion": 0.7,  "bits": 12, "rate": 16000},
    "retro":     {"gain_db": 0.0,  "distortion": 0.1,  "bits": 8,  "rate": 11000},
    "chaos":     {"gain_db": 20.0, "distortion": 1.0,  "bits": 5,  "rate": 4000},
}
OLD_PRESET_NAMES = {"Normál": "normal", "Hangos": "loud", "Rádió": "radio", "Telefon": "phone",
                    "Robot": "robot", "Megafon": "megaphone", "Retro 8-bit": "retro",
                    "Káosz": "chaos"}

LANGS = {"hu": "Magyar", "en": "English", "de": "Deutsch"}
TR = {
    "hu": {
        "preset": "Preset", "mic": "Mikrofon", "output": "Kimenet",
        "output_hint": "Discordhoz: CABLE Input", "api": "Hangrendszer",
        "gain": "Erősítés", "dist": "Torzítás", "bits": "Bitmélység", "rate": "Mintavétel",
        "meter_in": "Bemenet", "meter_out": "Kimenet",
        "live": "Élő",
        "idle": "Szünetel", "run": "Fut: {a} → {b}",
        "pick": "Válassz mikrofont és kimenetet!", "err": "Hiba: {e}",
        "mic_err": "Mikrofon hiba: {e}",
        "save_title": "Preset mentése", "save_prompt": "Preset neve:", "own": " (saját)",
        "settings": "Beállítások", "language": "Nyelv",
        "lang_note": "A nyelv azonnal érvényesül.", "close": "Bezár",
        "autostart": "Indítás a Windowsszal", "start_min": "Indítás kis méretben (tálcára)", "none": "(nincs)",
        "p_normal": "Normál", "p_loud": "Hangos", "p_radio": "Rádió", "p_phone": "Telefon",
        "p_robot": "Robot", "p_megaphone": "Megafon", "p_retro": "Retro 8-bit",
        "p_chaos": "Káosz",
    },
    "en": {
        "preset": "Preset", "mic": "Microphone", "output": "Output",
        "output_hint": "For Discord: CABLE Input", "api": "Audio system",
        "gain": "Gain", "dist": "Distortion", "bits": "Bit depth", "rate": "Sample rate",
        "meter_in": "Input", "meter_out": "Output",
        "live": "Live",
        "idle": "Paused", "run": "Running: {a} → {b}",
        "pick": "Select a microphone and an output!", "err": "Error: {e}",
        "mic_err": "Microphone error: {e}",
        "save_title": "Save preset", "save_prompt": "Preset name:", "own": " (custom)",
        "settings": "Settings", "language": "Language",
        "lang_note": "The language changes immediately.", "close": "Close",
        "autostart": "Start with Windows", "start_min": "Start minimized (to the taskbar)", "none": "(none)",
        "p_normal": "Normal", "p_loud": "Loud", "p_radio": "Radio", "p_phone": "Phone",
        "p_robot": "Robot", "p_megaphone": "Megaphone", "p_retro": "Retro 8-bit",
        "p_chaos": "Chaos",
    },
    "de": {
        "preset": "Voreinstellung", "mic": "Mikrofon", "output": "Ausgang",
        "output_hint": "Für Discord: CABLE Input", "api": "Audiosystem",
        "gain": "Verstärkung", "dist": "Verzerrung", "bits": "Bittiefe", "rate": "Abtastrate",
        "meter_in": "Eingang", "meter_out": "Ausgang",
        "live": "Live",
        "idle": "Pausiert", "run": "Läuft: {a} → {b}",
        "pick": "Wähle ein Mikrofon und einen Ausgang!", "err": "Fehler: {e}",
        "mic_err": "Mikrofonfehler: {e}",
        "save_title": "Voreinstellung speichern", "save_prompt": "Name der Voreinstellung:",
        "own": " (eigene)",
        "settings": "Einstellungen", "language": "Sprache",
        "lang_note": "Die Sprache wird sofort übernommen.", "close": "Schließen",
        "autostart": "Mit Windows starten", "start_min": "Minimiert starten (in die Taskleiste)",
        "none": "(keine)",
        "p_normal": "Normal", "p_loud": "Laut", "p_radio": "Radio", "p_phone": "Telefon",
        "p_robot": "Roboter", "p_megaphone": "Megafon", "p_retro": "Retro 8-Bit",
        "p_chaos": "Chaos",
    },
}

ACCENT = "#5865F2"
BG = "#16171c"
CARD = "#1f2128"
FIELD = "#2a2d37"
FIELD_HOVER = "#363a47"
MUTED = "#7d8299"
RED, GREEN = "#f04747", "#43b581"


RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def set_autostart(enabled: bool, minimized: bool) -> None:
    """Be-/kikapcsolja az indítást a Windowsszal (HKCU Run kulcs)."""
    if winreg is None:
        return
    if getattr(sys, "frozen", False):
        cmd = f'"{sys.executable}"'
    else:
        pyw = Path(sys.executable).with_name("pythonw.exe")
        cmd = f'"{pyw if pyw.exists() else sys.executable}" "{Path(__file__).resolve()}"'
    if minimized:
        cmd += " --minimized"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as k:
        if enabled:
            winreg.SetValueEx(k, "DSMic", 0, winreg.REG_SZ, cmd)
        else:
            try:
                winreg.DeleteValue(k, "DSMic")
            except FileNotFoundError:
                pass


def font(size, bold=False):
    return ("Segoe UI Semibold" if bold else "Segoe UI", size)


# --------------------------------------------------------------------------- DSP
class Processor:
    """Valós idejű jelfeldolgozó. A paraméterek bármikor módosíthatók a UI-ból."""

    def __init__(self):
        self.gain_db = 0.0
        self.distortion = 0.0   # 0..1
        self.bits = 16          # 2..16
        self.rate = 48000       # célmintavétel (Hz)
        self.peak = 0.0
        self.in_peak = 0.0
        self._counter = 0.0
        self._last = 0.0

    def process(self, x: np.ndarray, fs: float) -> np.ndarray:
        ip = float(np.max(np.abs(x))) if len(x) else 0.0
        self.in_peak = max(ip, self.in_peak * 0.85)
        x = x * (10.0 ** (self.gain_db / 20.0))

        # torzítás: tanh soft-clip, a "drive" a torzítás mértékével nő
        d = self.distortion
        if d > 0:
            drive = 1.0 + d * 40.0
            wet = np.tanh(x * drive) / np.tanh(drive)
            x = (1 - d) * x + d * wet

        # minőség 1: mintavételi frekvencia csökkentés (sample & hold)
        hold = fs / max(self.rate, 1000)
        if hold > 1.001:
            n = len(x)
            pos = np.floor((self._counter + np.arange(n)) / hold) * hold - self._counter
            ext = np.concatenate(([self._last], x))
            idx = np.clip(pos.astype(np.int64) + 1, 0, n)
            self._counter = (self._counter + n) % hold
            self._last = x[-1]
            x = ext[idx]

        # minőség 2: bitmélység csökkentés
        if self.bits < 16:
            levels = 2.0 ** (self.bits - 1)
            x = np.round(x * levels) / levels

        x = np.clip(x, -1.0, 1.0)
        self.peak = max(float(np.max(np.abs(x))) if len(x) else 0.0, self.peak * 0.85)
        return x.astype(np.float32)


# ------------------------------------------------------------------------ Audio
def list_apis():
    return [a["name"] for a in sd.query_hostapis()]


def list_devices(api_name: str, kind: str):
    """kind: 'input' vagy 'output'. Visszaadja a [(név, index)] listát."""
    apis = sd.query_hostapis()
    api_idx = next((i for i, a in enumerate(apis) if a["name"] == api_name), None)
    key = "max_input_channels" if kind == "input" else "max_output_channels"
    out = []
    for i, d in enumerate(sd.query_devices()):
        if d["hostapi"] == api_idx and d[key] > 0:
            out.append((d["name"], i))
    return out


class Engine:
    """Külön bemeneti és kimeneti stream, egy kis puffer köti össze őket."""

    MAX_BLOCKS = 8  # ennél több felgyülemlett blokknál eldobjuk a régit (késleltetés ellen)

    def __init__(self, proc: Processor):
        self.proc = proc
        self.streams = []
        self.buf = collections.deque()
        self.error = ""

    def start(self, in_idx: int, out_idx: int, api_name: str):
        self.stop()
        self.stop_preview()
        din, dout = sd.query_devices(in_idx), sd.query_devices(out_idx)
        fs = din["default_samplerate"]
        out_ch = min(2, dout["max_output_channels"])
        in_extra = out_extra = None
        if "WASAPI" in api_name:
            in_extra = sd.WasapiSettings(auto_convert=True)
            out_extra = sd.WasapiSettings(auto_convert=True)

        def in_cb(indata, frames, time, status):
            y = self.proc.process(indata[:, 0], fs)
            self.buf.append(y)
            while len(self.buf) > self.MAX_BLOCKS:
                self.buf.popleft()

        def out_cb(outdata, frames, time, status):
            try:
                y = self.buf.popleft()
            except IndexError:
                outdata.fill(0)
                return
            n = min(len(y), frames)
            outdata[:n] = y[:n, None]
            if n < frames:
                outdata[n:] = 0

        try:
            ins = sd.InputStream(device=in_idx, samplerate=fs, blocksize=BLOCK, channels=1,
                                 dtype="float32", latency="low", extra_settings=in_extra,
                                 callback=in_cb)
            outs = sd.OutputStream(device=out_idx, samplerate=fs, blocksize=BLOCK,
                                   channels=out_ch, dtype="float32", latency="low",
                                   extra_settings=out_extra, callback=out_cb)
            self.streams = [ins, outs]
            for st in self.streams:
                st.start()
        except Exception:
            self.stop()
            raise

    def preview(self, in_idx: int, api_name: str):
        """Csak figyeli a mikrofont (nincs kimenet), hogy a szintmérő indítás nélkül is mozogjon."""
        self.stop_preview()
        din = sd.query_devices(in_idx)
        fs = din["default_samplerate"]
        extra = sd.WasapiSettings(auto_convert=True) if "WASAPI" in api_name else None
        self.proc.in_peak = self.proc.peak = 0.0

        def cb(indata, frames, time, status):
            self.proc.process(indata[:, 0], fs)

        self._preview = sd.InputStream(device=in_idx, samplerate=fs, blocksize=BLOCK,
                                       channels=1, dtype="float32", extra_settings=extra,
                                       callback=cb)
        self._preview.start()

    def stop_preview(self):
        st = getattr(self, "_preview", None)
        self._preview = None
        if st is not None:
            try:
                st.stop()
                st.close()
            except Exception:
                pass

    def stop(self):
        for st in self.streams:
            try:
                st.stop()
                st.close()
            except Exception:
                pass
        self.streams = []
        self.buf.clear()
        self.proc.peak = 0.0
        self.proc.in_peak = 0.0

    @property
    def running(self):
        return bool(self.streams)


# --------------------------------------------------------------------------- UI
class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        ctk.set_appearance_mode("dark")
        self.title("DSMic")
        self.geometry("900x500")
        self.minsize(820, 480)
        self.configure(fg_color=BG)

        self.cfg = {**DEFAULTS, **self._load()}
        self.lang = self.cfg["lang"] if self.cfg["lang"] in LANGS else "hu"
        self._st = ("idle", {})
        self.live = True
        self.proc = Processor()
        self.engine = Engine(self.proc)
        self.devs_in, self.devs_out = [], []

        self._build()
        self._refresh_presets()
        self._refresh_devices()
        self._apply_params()
        self._apply_live()
        self.after(50, self._tick)
        self.protocol("WM_DELETE_WINDOW", self._close)
        if "--minimized" in sys.argv:
            self.after(400, self.iconify)
        if "--autostart" in sys.argv:
            self.after(10000, self._close)

    # -- config / nyelv
    def t(self, key, **kw):
        text = TR[self.lang].get(key) or TR["en"][key]
        return text.format(**kw) if kw else text

    def _load(self):
        try:
            return json.loads(CONFIG.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _collect(self):
        """A felület aktuális értékeit a cfg-be másolja."""
        self.cfg.update(
            api=self.api_var.get(),
            input=self.in_var.get(),
            output=self.out_var.get(),
            gain_db=self.gain.get(),
            distortion=self.dist.get(),
            bits=int(self.bits.get()),
            rate=int(self.rate.get() // 100 * 100),
            preset=self._preset_key(),
            lang=self.lang,
        )

    def _save(self):
        self._collect()
        CONFIG.write_text(json.dumps(self.cfg, indent=2), encoding="utf-8")

    def _set_lang(self, lang):
        if lang == self.lang:
            return
        self._collect()
        self.lang = lang
        self.cfg["lang"] = lang
        for w in self.winfo_children():
            if not isinstance(w, ctk.CTkToplevel):
                w.destroy()
        self._build()
        self._refresh_presets()
        self._refresh_devices()
        self._apply_params()
        self._render_status()
        self._save()

    def _open_settings(self):
        if getattr(self, "_dlg", None) is not None and self._dlg.winfo_exists():
            self._dlg.destroy()
        d = ctk.CTkToplevel(self, fg_color=BG)
        self._dlg = d
        d.title(self.t("settings"))
        d.geometry("360x320")
        d.resizable(False, False)
        d.transient(self)
        ctk.CTkLabel(d, text=self.t("settings"), font=font(18, True)).pack(
            anchor="w", padx=24, pady=(22, 14))
        ctk.CTkLabel(d, text=self.t("language"), font=font(11), text_color=MUTED).pack(
            anchor="w", padx=24)
        var = ctk.StringVar(value=LANGS[self.lang])

        def pick(name):
            code = next(c for c, n in LANGS.items() if n == name)
            self._set_lang(code)
            self._open_settings()  # a párbeszédablak is az új nyelven jelenjen meg

        ctk.CTkOptionMenu(d, variable=var, values=list(LANGS.values()), command=pick,
                          fg_color=FIELD, button_color=FIELD, button_hover_color=FIELD_HOVER,
                          dropdown_fg_color=FIELD, dropdown_hover_color=FIELD_HOVER,
                          font=font(13), dropdown_font=font(13), height=34,
                          corner_radius=8, anchor="w").pack(fill="x", padx=24, pady=(4, 6))
        ctk.CTkLabel(d, text=self.t("lang_note"), font=font(11), text_color=MUTED).pack(
            anchor="w", padx=24)

        ctk.CTkFrame(d, height=1, fg_color=FIELD).pack(fill="x", padx=24, pady=(18, 6))
        auto_var = ctk.BooleanVar(value=bool(self.cfg["autostart"]))
        min_var = ctk.BooleanVar(value=bool(self.cfg["start_min"]))

        def apply_auto():
            self.cfg["autostart"] = bool(auto_var.get())
            self.cfg["start_min"] = bool(min_var.get())
            try:
                set_autostart(self.cfg["autostart"], self.cfg["start_min"])
            except OSError as e:
                self._set_status("err", e=e)
            self._save()

        for text, var in ((self.t("autostart"), auto_var), (self.t("start_min"), min_var)):
            ctk.CTkSwitch(d, text=text, variable=var, command=apply_auto, font=font(12),
                          progress_color=ACCENT, button_color="white", fg_color=FIELD,
                          switch_width=40, switch_height=20).pack(anchor="w", padx=24, pady=8)
        d.after(150, d.focus)

    # -- layout
    def _label(self, parent, text, pady=(16, 5)):
        ctk.CTkLabel(parent, text=text, font=font(11), text_color=MUTED
                     ).pack(anchor="w", pady=pady)

    def _menu(self, parent, var, command=None, **pack):
        m = ctk.CTkOptionMenu(parent, variable=var, values=[""], fg_color=FIELD,
                              button_color=FIELD, button_hover_color=FIELD_HOVER,
                              dropdown_fg_color=FIELD, dropdown_hover_color=FIELD_HOVER,
                              font=font(12), dropdown_font=font(12),
                              height=34, corner_radius=8, dynamic_resizing=False,
                              anchor="w", command=command)
        m.pack(**({"fill": "x"} | pack))
        return m

    def _slider(self, parent, row, col, label, lo, hi, value, fmt, steps=None):
        box = ctk.CTkFrame(parent, fg_color="transparent")
        box.grid(row=row, column=col, sticky="ew", padx=16, pady=12)
        head = ctk.CTkFrame(box, fg_color="transparent")
        head.pack(fill="x")
        ctk.CTkLabel(head, text=label, font=font(13)).pack(side="left")
        val = ctk.CTkLabel(head, text="", font=font(13, True), text_color=ACCENT)
        val.pack(side="right")

        def changed(v):
            val.configure(text=fmt(v))
            self._apply_params()

        s = ctk.CTkSlider(box, from_=lo, to=hi, number_of_steps=steps, command=changed,
                          height=16, progress_color=ACCENT, button_color="white",
                          button_hover_color="#dfe1ff", fg_color=FIELD)
        s.set(value)
        s.pack(fill="x", pady=(8, 0))
        val.configure(text=fmt(value))
        s.set_value = lambda v: (s.set(v), val.configure(text=fmt(v)))
        return s

    def _build(self):
        self.title("DSMic")
        self.grid_columnconfigure(0, weight=0, minsize=290)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # ---- bal oldal: preset + eszközök
        left = ctk.CTkFrame(self, fg_color="transparent", width=290)
        left.grid(row=0, column=0, sticky="nsew", padx=(26, 12), pady=22)
        left.grid_propagate(False)
        top = ctk.CTkFrame(left, fg_color="transparent")
        top.pack(fill="x")
        ctk.CTkLabel(top, text="DSMic", font=("Segoe UI Light", 30),
                     text_color="white").pack(side="left")
        ctk.CTkButton(top, text="⚙", width=34, height=34, corner_radius=8, fg_color="transparent",
                      hover_color=FIELD, text_color=MUTED, font=font(17),
                      command=self._open_settings).pack(side="right")

        self._label(left, self.t("preset"), pady=(14, 5))
        prow = ctk.CTkFrame(left, fg_color="transparent")
        prow.pack(fill="x")
        self.preset_var = ctk.StringVar()
        self.preset_menu = self._menu(prow, self.preset_var, self._apply_preset,
                                      side="left", fill="x", expand=True)
        ctk.CTkButton(prow, text="＋", width=34, height=34, corner_radius=8, fg_color=FIELD,
                      hover_color=ACCENT, font=font(14),
                      command=self._save_preset).pack(side="left", padx=(6, 0))
        self.del_btn = ctk.CTkButton(prow, text="✕", width=34, height=34, corner_radius=8,
                                     fg_color=FIELD, hover_color=RED, font=font(12),
                                     command=self._delete_preset)
        self.del_btn.pack(side="left", padx=(6, 0))

        self.api_var = ctk.StringVar(value=self.cfg["api"])
        self.in_var = ctk.StringVar(value=self.cfg["input"])
        self.out_var = ctk.StringVar(value=self.cfg["output"])
        self._label(left, self.t("mic"))
        self.in_menu = self._menu(left, self.in_var, lambda _: self._apply_live())
        self._label(left, f"{self.t('output')}  ·  {self.t('output_hint')}")
        self.out_menu = self._menu(left, self.out_var, lambda _: self._apply_live())
        self._label(left, self.t("api"))
        self.api_menu = self._menu(
            left, self.api_var,
            lambda _: (self._refresh_devices(keep_api=True), self._apply_live()))

        # ---- jobb oldal: beállítások, mérők, indítás
        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(12, 26), pady=22)

        card = ctk.CTkFrame(right, fg_color=CARD, corner_radius=16)
        card.pack(fill="x")
        card.grid_columnconfigure((0, 1), weight=1, uniform="c")
        self.gain = self._slider(card, 0, 0, self.t("gain"), -20, 40, self.cfg["gain_db"],
                                 lambda v: f"{v:+.1f} dB")
        self.dist = self._slider(card, 0, 1, self.t("dist"), 0, 1, self.cfg["distortion"],
                                 lambda v: f"{v * 100:.0f} %")
        self.bits = self._slider(card, 1, 0, self.t("bits"), 2, 16, self.cfg["bits"],
                                 lambda v: f"{int(v)} bit", steps=14)
        self.rate = self._slider(card, 1, 1, self.t("rate"), 2000, 48000, self.cfg["rate"],
                                 lambda v: f"{int(v / 100) * 100} Hz", steps=46)

        meters = ctk.CTkFrame(right, fg_color=CARD, corner_radius=16)
        meters.pack(fill="x", pady=(14, 0))
        self.meters = {}
        for key, text in (("in", self.t("meter_in")), ("out", self.t("meter_out"))):
            row = ctk.CTkFrame(meters, fg_color="transparent")
            row.pack(fill="x", padx=18, pady=(12 if key == "in" else 4, 12 if key == "out" else 4))
            ctk.CTkLabel(row, text=text, width=70, anchor="w", font=font(12),
                         text_color=MUTED).pack(side="left")
            bar = ctk.CTkProgressBar(row, height=8, progress_color=GREEN, fg_color=FIELD)
            bar.set(0)
            bar.pack(side="left", fill="x", expand=True, padx=10)
            lab = ctk.CTkLabel(row, text="-inf", width=52, anchor="e",
                               font=font(12, True), text_color=ACCENT)
            lab.pack(side="right")
            self.meters[key] = (bar, lab)

        self.status = ctk.CTkLabel(right, text="", font=font(12), text_color=MUTED,
                                   anchor="w", wraplength=520)
        self.status.pack(side="bottom", anchor="w", pady=(8, 0))
        live = ctk.CTkFrame(right, fg_color=CARD, corner_radius=16)
        live.pack(side="bottom", fill="x")
        ctk.CTkLabel(live, text=self.t("live"), font=font(14, True)).pack(
            side="left", padx=(20, 0), pady=16)
        self.live_var = ctk.BooleanVar(value=self.live)
        ctk.CTkSwitch(live, text="", variable=self.live_var, width=48, switch_width=44,
                      switch_height=22, progress_color=GREEN, button_color="white",
                      fg_color=FIELD, command=self._toggle_live).pack(side="right", padx=20)

    # -- logic
    def _refresh_devices(self, keep_api=False):
        apis = list_apis()
        pref = self.api_var.get() or self.cfg["api"]
        if pref not in apis:
            pref = next((a for a in apis if "WASAPI" in a), apis[0])
        self.api_var.set(pref)
        self.api_menu.configure(values=apis)

        self.devs_in = list_devices(pref, "input")
        self.devs_out = list_devices(pref, "output")
        ins = [n for n, _ in self.devs_in] or [self.t("none")]
        outs = [n for n, _ in self.devs_out] or [self.t("none")]
        self.in_menu.configure(values=ins)
        self.out_menu.configure(values=outs)

        if self.in_var.get() not in ins:
            default_in = sd.default.device[0]
            name = next((n for n, i in self.devs_in if i == default_in), ins[0])
            self.in_var.set(name)
        if self.out_var.get() not in outs:
            cable = next((n for n in outs if "CABLE Input" in n), None)
            self.out_var.set(cable or outs[0])

    # -- presetek
    def _preset_names(self):
        """{megjelenő név: azonosító}; a beépítettek neve nyelvfüggő."""
        names = {self.t(f"p_{k}"): k for k in BUILTIN_PRESETS}
        names.update({n: n for n in self.cfg.get("presets", {})})
        return names

    def _preset_values(self, key):
        return BUILTIN_PRESETS.get(key) or self.cfg.get("presets", {}).get(key)

    def _preset_key(self):
        return self._preset_names().get(self.preset_var.get(), "normal")

    def _show_preset(self, key):
        names = self._preset_names()
        self.preset_var.set(next((n for n, k in names.items() if k == key), self.t("p_normal")))

    def _refresh_presets(self):
        key = OLD_PRESET_NAMES.get(self.cfg["preset"], self.cfg["preset"])
        if self._preset_values(key) is None:
            key = "normal"
        self.preset_menu.configure(values=list(self._preset_names()))
        self._show_preset(key)
        self.del_btn.configure(
            state="normal" if key in self.cfg.get("presets", {}) else "disabled")

    def _apply_preset(self, _=None):
        key = self._preset_key()
        p = self._preset_values(key)
        if p:
            self.gain.set_value(p["gain_db"])
            self.dist.set_value(p["distortion"])
            self.bits.set_value(p["bits"])
            self.rate.set_value(p["rate"])
            self._apply_params()
        self.cfg["preset"] = key
        self._refresh_presets()

    def _save_preset(self):
        dlg = ctk.CTkInputDialog(text=self.t("save_prompt"), title=self.t("save_title"))
        name = (dlg.get_input() or "").strip()[:30]
        if not name:
            return
        if name in self._preset_names() and name not in self.cfg.get("presets", {}):
            name += self.t("own")
        self.cfg.setdefault("presets", {})[name] = {
            "gain_db": round(float(self.gain.get()), 1),
            "distortion": round(float(self.dist.get()), 2),
            "bits": int(round(self.bits.get())),
            "rate": int(self.rate.get() // 100 * 100),
        }
        self.cfg["preset"] = name
        self._refresh_presets()
        self._save()

    def _delete_preset(self):
        key = self._preset_key()
        if key in self.cfg.get("presets", {}):
            del self.cfg["presets"][key]
            self.cfg["preset"] = "normal"
            self._refresh_presets()
            self._apply_preset()
            self._save()

    def _restart_preview(self, *_):
        if self.engine.running:
            return
        idx = dict(self.devs_in).get(self.in_var.get())
        if idx is None:
            return
        try:
            self.engine.preview(idx, self.api_var.get())
        except Exception as e:  # noqa: BLE001
            self._set_status("mic_err", e=e)

    def _apply_params(self):
        if not hasattr(self, "rate"):
            return
        p = self.proc
        p.gain_db = float(self.gain.get())
        p.distortion = float(self.dist.get())
        p.bits = int(round(self.bits.get()))
        p.rate = int(self.rate.get() // 100 * 100)

    # -- állapot
    def _set_status(self, kind, **kw):
        self._st = (kind, kw)
        self._render_status()

    def _render_status(self):
        kind, kw = self._st
        color = GREEN if kind == "run" else MUTED if kind == "idle" else RED
        self.status.configure(text=self.t(kind, **kw) if kw else self.t(kind), text_color=color)

    def _toggle_live(self):
        self.live = bool(self.live_var.get())
        self._apply_live()

    def _apply_live(self):
        """Újraindítja a hangot az aktuális eszközökkel; kikapcsolt állapotban csak a szintmérő megy."""
        self.engine.stop()
        self.engine.stop_preview()
        idx_in = dict(self.devs_in).get(self.in_var.get())
        idx_out = dict(self.devs_out).get(self.out_var.get())
        if self.live and idx_in is not None and idx_out is not None:
            try:
                self.engine.start(idx_in, idx_out, self.api_var.get())
                self._set_status("run", a=self.in_var.get(), b=self.out_var.get())
                return
            except Exception as e:  # noqa: BLE001
                self._set_status("err", e=e)
        elif self.live:
            self._set_status("pick")
        else:
            self._set_status("idle")
        self._restart_preview()

    def _tick(self):
        if "--autostart" in sys.argv:
            with open(BASE / "dsmic.log", "a", encoding="utf-8") as f:
                f.write(f"running={self.engine.running} in={self.proc.in_peak:.5f} "
                        f"out={self.proc.peak:.5f} dev={self.in_var.get()}|{self.out_var.get()}"
                        f"|{self.api_var.get()} status={self.status.cget('text')}\n")
        for key, peak in (("in", self.proc.in_peak), ("out", self.proc.peak)):
            bar, lab = self.meters[key]
            db = 20 * np.log10(peak) if peak > 1e-6 else -90.0
            bar.set(max(0.0, min(1.0, (db + 60) / 60)))
            bar.configure(progress_color="#f04747" if db > -1 else
                          "#faa61a" if db > -12 else "#43b581")
            lab.configure(text=f"{db:.0f} dB" if db > -90 else "-inf")
        self.after(50, self._tick)

    def _close(self):
        self.engine.stop()
        self.engine.stop_preview()
        self._save()
        self.destroy()


if __name__ == "__main__":
    App().mainloop()
