import os
import sys
import threading
import wave
import pyaudio
import json
import subprocess
import customtkinter as ctk
from PIL import Image
# To fix DLL loading issues in PyInstaller for PyAV (av)
try:
    import av
    import av._core
except (ImportError, FileNotFoundError):
    # If av.libs is missing in a frozen environment, faster-whisper might still work
    # if it uses its own internal libraries or if we are just collecting metadata.
    pass 
from faster_whisper import WhisperModel

# To fix CustomTkinter theme issues in PyInstaller, we must ensure it can find its assets
import customtkinter as ctk
if getattr(sys, 'frozen', False):
    # Manually tell CustomTkinter where the themes are if the default detection fails
    ctk_path = os.path.join(sys._MEIPASS, "customtkinter")
    if os.path.exists(ctk_path):
        ctk.set_appearance_mode("dark") # Initialize basic settings early
from pynput import keyboard
import time
from tkinter import filedialog

# Configuration constants
class AppConfig:
    # Audio settings
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000

    # UI colors
    PRIMARY_BG = "#121212"
    TITLE_BAR_BG = "#1f1f1f"
    TEXT_AREA_BG = "#1e1e1e"
    SECONDARY_BG = "#34495e"
    BORDER_COLOR = "#333333"
    ACCENT_COLOR = "#3498db"
    ACCENT_HOVER = "#2980b9"
    RECORD_BTN_COLOR = "#2ecc71"
    RECORD_BTN_HOVER = "#27ae60"
    STOP_BTN_COLOR = "#e74c3c"
    STOP_BTN_HOVER = "#c0392b"
    PROGRESS_BG = "#2c2c2c"
    UI_GRAY = "#555555"
    
    # Text colors
    TEXT_COLOR_SECONDARY = "#888888"
    WARNING_COLOR = "#f1c40f"
    SUCCESS_COLOR = "#2ecc71"
    ERROR_COLOR = "#e74c3c"
    ORANGE_COLOR = "#e67e22"

    # Fonts
    FONT_FAMILY = "Segoe UI"
    TITLE_FONT_SIZE = 13
    STATUS_FONT_SIZE = 11
    TEXT_FONT_SIZE = 12

    # App
    DEFAULT_GEOMETRY = "350x450+100+100"
    ICON_PATH_ICO = "icon.ico"
    ICON_PATH_PNG = "icon.png"
    TEMP_AUDIO_FILE = "temp_cache.wav"
    CONFIG_FILE = "config.json"

# Configuration for Bundling
def get_resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class SpeechWidget(ctk.CTk):
    def __init__(self):
        super().__init__()

        # --- Window Settings ---
        self.title("sOuLSPEECH")
        try:
            # Set window/taskbar icon using PNG
            icon_path_png = get_resource_path(AppConfig.ICON_PATH_PNG)
            if os.path.exists(icon_path_png):
                from PIL import ImageTk
                img = Image.open(icon_path_png)
                self.app_icon = ImageTk.PhotoImage(img)
                self.wm_iconphoto(True, self.app_icon)
                
                # Fix for Windows taskbar icon display
                if os.name == 'nt':
                    import ctypes
                    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("soulspeech.whisper.app")
            
            # Try to set .ico for Windows specifically if it exists
            icon_path_ico = get_resource_path(AppConfig.ICON_PATH_ICO)
            if os.path.exists(icon_path_ico):
                self.iconbitmap(icon_path_ico)
        except Exception as e:
            print(f"Error loading application icon: {e}")
        
        # --- Variables & Config ---
        self.is_recording = False
        self.is_minimized = False
        self.keyboard = keyboard.Controller()
        self.hotkey_listener = None
        self.audio_frames = []
        self.stream = None
        self.p = pyaudio.PyAudio()
        self.config_file = AppConfig.CONFIG_FILE
        self.selected_input_device_index = None

        # Load settings from file or use defaults
        self.load_config()
        self.geometry(self.last_expanded_geo)

        self.overrideredirect(True)      
        self.attributes("-topmost", True) 
        self.attributes("-alpha", 0.95)   
        self.configure(fg_color=AppConfig.PRIMARY_BG)

        # Load Icon for minimized button
        self.mic_icon = None
        try:
            icon_path = get_resource_path(AppConfig.ICON_PATH_PNG)
            if os.path.exists(icon_path):
                img = Image.open(icon_path)
                # Ensure the image is in RGBA for transparency support and properly resized
                if img.mode != 'RGBA':
                    img = img.convert('RGBA')
                # Slightly larger size for the 60x60 floating button (40x40)
                self.mic_icon = ctk.CTkImage(light_image=img, dark_image=img, size=(40, 40))
        except Exception as e:
            print(f"Error loading minimized icon: {e}")
        
        # Load Model Offline (Threaded)
        self.model = None
        
        self.setup_ui()
        self.setup_bindings()
        
        # Start model loading in a thread to prevent UI freeze
        threading.Thread(target=self._load_whisper_model, daemon=True).start()
        
        self.setup_hotkey_listener()

    def load_config(self):
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config = json.load(f)
                    self.last_expanded_geo = config.get('last_geometry', AppConfig.DEFAULT_GEOMETRY)
                    self.whisper_device = config.get('whisper_device', 'cpu')
                    self.whisper_compute_type = config.get('whisper_compute_type', 'int8')
                    self.whisper_language = config.get('whisper_language', None)
                    self.global_hotkey = config.get('global_hotkey', "<ctrl>+<alt>+s")
                    self.hotkey_enabled = config.get('hotkey_enabled', True)
            else:
                raise FileNotFoundError
        except Exception:
            # Default values if config is missing or invalid
            self.last_expanded_geo = AppConfig.DEFAULT_GEOMETRY
            self.whisper_device = "cpu"
            self.whisper_compute_type = "int8"
            self.whisper_language = None
            self.global_hotkey = "<ctrl>+<alt>+s"
            self.hotkey_enabled = True

    def save_config(self):
        current_geo = self.geometry()
        # If minimized, use the last known expanded geometry to save
        save_geo = self.last_expanded_geo if self.is_minimized else current_geo
        
        config = {
            'last_geometry': save_geo,
            'whisper_device': self.whisper_device,
            'whisper_compute_type': self.whisper_compute_type,
            'whisper_language': self.whisper_language,
            'global_hotkey': self.global_hotkey,
            'hotkey_enabled': self.hotkey_enabled
        }
        try:
            with open(self.config_file, 'w') as f:
                json.dump(config, f, indent=4)
        except Exception as e:
            print(f"Error saving config: {e}")

    def setup_ui(self):
        # Clear existing widgets if any (for toggle)
        for widget in self.winfo_children():
            widget.destroy()

        if self.is_minimized:
            self.setup_minimized_ui()
        else:
            self.setup_expanded_ui()

    def setup_expanded_ui(self):
        self.geometry(self.last_expanded_geo)
        self.configure(fg_color=AppConfig.PRIMARY_BG)

        # Custom Title Bar
        title_bar = ctk.CTkFrame(self, fg_color=AppConfig.TITLE_BAR_BG, height=35, corner_radius=0)
        title_bar.pack(fill="x", side="top")
        
        title_label = ctk.CTkLabel(title_bar, text="sOuLSPEECH", font=(AppConfig.FONT_FAMILY, AppConfig.TITLE_FONT_SIZE, "bold"), text_color=AppConfig.ACCENT_COLOR)
        title_label.pack(side="left", padx=10)

        close_btn = ctk.CTkButton(title_bar, text="✕", width=30, height=30, fg_color="transparent", 
                                  hover_color=AppConfig.STOP_BTN_COLOR, command=self.quit)
        close_btn.pack(side="right", padx=2)

        settings_btn = ctk.CTkButton(title_bar, text="⚙", width=30, height=30, fg_color="transparent", 
                                     hover_color=AppConfig.SECONDARY_BG, command=self.open_settings)
        settings_btn.pack(side="right", padx=2)

        min_btn = ctk.CTkButton(title_bar, text="—", width=30, height=30, fg_color="transparent", 
                                hover_color=AppConfig.SECONDARY_BG, command=self.toggle_minimize)
        min_btn.pack(side="right", padx=2)

        # Main Content
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=15, pady=10)

        initial_status = "Ready to Listen" if self.model else "Loading A.I. Model..."
        initial_color = AppConfig.TEXT_COLOR_SECONDARY if self.model else AppConfig.WARNING_COLOR
        initial_state = "normal" if self.model else "disabled"

        self.status_label = ctk.CTkLabel(main_frame, text=initial_status, font=(AppConfig.FONT_FAMILY, AppConfig.STATUS_FONT_SIZE), text_color=initial_color)
        self.status_label.pack(pady=(0, 5))

        self.progress_bar = ctk.CTkProgressBar(main_frame, height=8, fg_color=AppConfig.PROGRESS_BG, progress_color=AppConfig.ACCENT_COLOR)
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=5)

        self.text_area = ctk.CTkTextbox(main_frame, font=(AppConfig.FONT_FAMILY, AppConfig.TEXT_FONT_SIZE), fg_color=AppConfig.TEXT_AREA_BG, border_width=1, border_color=AppConfig.BORDER_COLOR)
        self.text_area.pack(expand=True, fill="both", pady=10)

        btn_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_row.pack(fill="x")

        self.record_btn = ctk.CTkButton(btn_row, text="START RECORDING", command=self.toggle_record, 
                                        fg_color=AppConfig.RECORD_BTN_COLOR, hover_color=AppConfig.RECORD_BTN_HOVER, font=(AppConfig.FONT_FAMILY, AppConfig.TEXT_FONT_SIZE, "bold"), height=40, state=initial_state)
        self.record_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.import_btn = ctk.CTkButton(btn_row, text="IMPORT", command=self.import_audio, 
                                        fg_color=AppConfig.ACCENT_COLOR, width=70, height=40, state=initial_state)
        self.import_btn.pack(side="right")

        copy_btn = ctk.CTkButton(main_frame, text="COPY TEXT", command=self.copy_to_clipboard, 
                                 fg_color=AppConfig.SECONDARY_BG, height=30)
        copy_btn.pack(fill="x", pady=(10, 0))

        clear_btn = ctk.CTkButton(main_frame, text="CLEAR TEXT", command=self.clear_text_area,
                                  fg_color=AppConfig.UI_GRAY, height=30)
        clear_btn.pack(fill="x", pady=(5, 0))

    def setup_minimized_ui(self):
        # Save current position before shrinking
        self.last_expanded_geo = self.geometry()
        
        # Make circular-ish small floating button
        size = 60
        self.geometry(f"{size}x{size}")
        
        # Use icon if loaded, otherwise fallback to "S"
        btn_kwargs = {
            "fg_color": AppConfig.ACCENT_COLOR,
            "hover_color": AppConfig.ACCENT_HOVER,
            "corner_radius": size // 2,
            "width": size,
            "height": size,
            "border_width": 0,
            "command": self.toggle_minimize
        }
        
        if self.mic_icon:
            # Force empty text and center the image
            self.icon_label = ctk.CTkButton(self, text="", image=self.mic_icon, compound="center", **btn_kwargs)
        else:
            self.icon_label = ctk.CTkButton(self, text="S", font=(AppConfig.FONT_FAMILY, 24, "bold"), **btn_kwargs)
            
        self.icon_label.pack(expand=True, fill="both")

    def toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        self.setup_ui()
        self.setup_bindings()

    def setup_bindings(self):
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)

    def quit(self):
        """Gracefully terminate PyAudio and close the application."""
        self.save_config()
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
        if self.stream:
            try:
                if self.stream.is_active():
                    self.stream.stop_stream()
                self.stream.close()
            except Exception:
                pass
        if self.p:
            try:
                self.p.terminate()
            except Exception:
                pass
        super().quit()
        self.destroy()

    def _load_whisper_model(self):
        model_path = get_resource_path("model_files")
        if not os.path.exists(model_path):
            self.after(0, lambda: self._update_ui_on_model_error(f"Model directory not found at {model_path}"))
            return

        try:
            # The model loading can take several seconds
            self.model = WhisperModel(
                model_path, 
                device=self.whisper_device, 
                compute_type=self.whisper_compute_type
            )
            self.after(0, self._update_ui_on_model_ready)
        except Exception as e:
            error_msg = str(e)
            if "cuda" in error_msg.lower():
                error_msg = "CUDA error: Ensure NVIDIA drivers/cuDNN are installed or switch to CPU in settings."
            elif "out of memory" in error_msg.lower():
                error_msg = "GPU Out of Memory: Try using 'int8' compute type or CPU."
            
            print(f"Whisper Model Loading Error: {e}") 
            self.after(0, lambda err=error_msg: self._update_ui_on_model_error(err))

    def _update_ui_on_model_ready(self):
        if not self.is_minimized:
            self.status_label.configure(text="Ready to Listen", text_color=AppConfig.TEXT_COLOR_SECONDARY)
            self.record_btn.configure(state="normal")
            self.import_btn.configure(state="normal")

    def _update_ui_on_model_error(self, error_msg):
        if not self.is_minimized:
            self.status_label.configure(text=f"Model Error: {error_msg}", text_color=AppConfig.ERROR_COLOR)
            self.record_btn.configure(state="disabled")
            self.import_btn.configure(state="disabled")

    def setup_hotkey_listener(self):
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
            self.hotkey_listener = None
            
        if self.hotkey_enabled and self.global_hotkey:
            try:
                self.hotkey_listener = keyboard.GlobalHotKeys({
                    self.global_hotkey: self.on_hotkey_pressed
                })
                self.hotkey_listener.start()
            except Exception as e:
                print(f"Error setting up hotkey: {e}")

    def on_hotkey_pressed(self):
        # Ensure UI updates are on the main thread
        self.after(0, self.toggle_record)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        self.geometry(f"+{self.winfo_x() + deltax}+{self.winfo_y() + deltay}")

    def copy_to_clipboard(self):
        text = self.text_area.get("1.0", "end-1c")
        self.clipboard_clear()
        self.clipboard_append(text)
        self.status_label.configure(text="Copied to clipboard!", text_color=AppConfig.SUCCESS_COLOR)
        self.after(2000, lambda: self.status_label.configure(text="Ready", text_color=AppConfig.TEXT_COLOR_SECONDARY))

    def clear_text_area(self):
        self.text_area.delete("1.0", "end")
        self.status_label.configure(text="Text cleared.", text_color=AppConfig.TEXT_COLOR_SECONDARY)

    # --- Core Logic ---
    def toggle_record(self):
        if self.model is None:
            return
        if not self.is_recording:
            self.is_recording = True
            self.record_btn.configure(text="STOP", fg_color=AppConfig.STOP_BTN_COLOR)
            self.status_label.configure(text="Recording...", text_color=AppConfig.ERROR_COLOR)
            self.progress_bar.set(0)
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
            threading.Thread(target=self.record_audio).start()
        else:
            self.is_recording = False
            self.record_btn.configure(text="PROCESSING...", state="disabled")
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")

    def record_audio(self):
        try:
            self.stream = self.p.open(
                format=AppConfig.FORMAT, 
                channels=AppConfig.CHANNELS, 
                rate=AppConfig.RATE, 
                input=True, 
                frames_per_buffer=AppConfig.CHUNK,
                input_device_index=self.selected_input_device_index
            )
            self.audio_frames = []

            while self.is_recording:
                data = self.stream.read(AppConfig.CHUNK)
                self.audio_frames.append(data)

            self.stream.stop_stream()
            self.stream.close()
            
            temp_file = AppConfig.TEMP_AUDIO_FILE
            wf = wave.open(temp_file, 'wb')
            wf.setnchannels(AppConfig.CHANNELS)
            wf.setsampwidth(self.p.get_sample_size(AppConfig.FORMAT))
            wf.setframerate(AppConfig.RATE)
            wf.writeframes(b''.join(self.audio_frames))
            wf.close()

            self.process_audio(temp_file)
        except Exception as e:
            self.is_recording = False
            error_msg = str(e)
            if "Invalid number of channels" in error_msg:
                error_msg = "Mic Error: Invalid channels. Try a different device in settings."
            elif "Device not found" in error_msg:
                error_msg = "Mic Error: Device not found. Check connections."
            
            print(f"Recording Error: {e}")
            self.after(0, lambda: self.status_label.configure(text=f"Recording Error: {error_msg}", text_color=AppConfig.ERROR_COLOR))
            self.after(0, self._reset_record_button)

    def process_audio(self, file_path):
        self.after(0, lambda: self.status_label.configure(text="Transcribing... 0%", text_color=AppConfig.WARNING_COLOR))
        self.after(0, lambda: self.progress_bar.set(0))
        
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"Audio file not found: {file_path}")

            duration = 0
            try:
                with wave.open(file_path, 'rb') as f:
                    duration = f.getnframes() / float(f.getframerate())
            except Exception:
                pass 

            segments, info = self.model.transcribe(
                file_path, 
                beam_size=5, 
                language=self.whisper_language
            )
            full_text = ""
            
            for segment in segments:
                full_text += segment.text + " "
                if duration > 0:
                    progress = min(segment.end / duration, 1.0)
                    self.after(0, lambda p=progress: self.update_progress(p))
                
                self.after(0, lambda t=full_text: self.update_text_area(t))

            if not full_text.strip():
                self.after(0, lambda: self.status_label.configure(text="No speech detected.", text_color=AppConfig.ORANGE_COLOR))
                self.after(0, self._reset_record_button)
            else:
                self.after(0, lambda: self.finalize_transcription(full_text.strip()))

        except Exception as e:
            print(f"Transcription Error: {e}")
            error_msg = str(e)
            if "float16" in error_msg.lower() and self.whisper_device == "cpu":
                error_msg = "CPU does not support float16. Change compute type to int8."
            
            self.after(0, lambda: self.status_label.configure(text=f"Transcription Error: {error_msg}", text_color=AppConfig.ERROR_COLOR))
            self.after(0, self._reset_record_button)
        finally:
            if AppConfig.TEMP_AUDIO_FILE in file_path and os.path.exists(file_path):
                try:
                    os.remove(file_path)
                except Exception:
                    pass
        
    def update_progress(self, val):
        self.progress_bar.set(val)
        self.status_label.configure(text=f"Transcribing... {int(val*100)}%")

    def update_text_area(self, text):
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", text)
        self.text_area.see("end")

    def finalize_transcription(self, text):
        self._reset_record_button()
        self.status_label.configure(text="Transcription Complete", text_color=AppConfig.SUCCESS_COLOR)
        self.progress_bar.set(1.0)
        # Optional: Auto-type out as before
        # threading.Thread(target=self.type_out, args=(text,)).start()

    def _reset_record_button(self):
        self.record_btn.configure(text="START RECORDING", state="normal", fg_color=AppConfig.RECORD_BTN_COLOR)

    def get_audio_input_devices(self):
        devices = []
        try:
            info = self.p.get_host_api_info_by_index(0)
            num_devices = info.get('deviceCount', 0)
            for i in range(num_devices):
                device_info = self.p.get_device_info_by_host_api_device_index(0, i)
                if device_info.get('maxInputChannels', 0) > 0:
                    devices.append({'name': device_info.get('name'), 'index': i})
        except Exception:
            pass
        return devices

    def open_settings(self):
        settings_win = ctk.CTkToplevel(self)
        settings_win.title("Settings")
        settings_win.geometry("320x600")
        settings_win.attributes("-topmost", True)
        settings_win.configure(fg_color=AppConfig.PRIMARY_BG)

        # Create a scrollable frame for settings
        scroll_frame = ctk.CTkScrollableFrame(settings_win, fg_color="transparent")
        scroll_frame.pack(expand=True, fill="both", padx=5, pady=5)

        ctk.CTkLabel(scroll_frame, text="Settings", font=(AppConfig.FONT_FAMILY, 16, "bold")).pack(pady=15)

        # Input Device
        ctk.CTkLabel(scroll_frame, text="Microphone:").pack(pady=(5, 0))
        input_devices = self.get_audio_input_devices()
        device_names = [d['name'] for d in input_devices]
        
        current_device_name = "Default"
        if self.selected_input_device_index is not None:
            for d in input_devices:
                if d['index'] == self.selected_input_device_index:
                    current_device_name = d['name']
                    break
        
        input_device_var = ctk.StringVar(value=current_device_name)
        input_device_menu = ctk.CTkOptionMenu(scroll_frame, values=["Default"] + device_names, variable=input_device_var)
        input_device_menu.pack(pady=5)

        # Device
        ctk.CTkLabel(scroll_frame, text="A.I. Compute Device:").pack(pady=(10, 0))
        device_var = ctk.StringVar(value=self.whisper_device)
        device_menu = ctk.CTkOptionMenu(scroll_frame, values=["cpu", "cuda"], variable=device_var)
        device_menu.pack(pady=5)

        # Compute Type
        ctk.CTkLabel(scroll_frame, text="Compute Type:").pack(pady=(10, 0))
        compute_var = ctk.StringVar(value=self.whisper_compute_type)
        compute_menu = ctk.CTkOptionMenu(scroll_frame, values=["int8", "float16", "float32", "int8_float16"], variable=compute_var)
        compute_menu.pack(pady=5)

        # Hotkey
        ctk.CTkLabel(scroll_frame, text="Global Hotkey:").pack(pady=(10, 0))
        hotkey_var = ctk.StringVar(value=self.global_hotkey)
        hotkey_entry = ctk.CTkEntry(scroll_frame, textvariable=hotkey_var)
        hotkey_entry.pack(pady=5)
        
        def on_key_press(event):
            modifiers = {
                'Control_L': '<ctrl>', 'Control_R': '<ctrl>',
                'Alt_L': '<alt>', 'Alt_R': '<alt>',
                'Shift_L': '<shift>', 'Shift_R': '<shift>',
                'Win_L': '<cmd>', 'Win_R': '<cmd>'
            }
            parts = []
            if event.state & 0x0004: parts.append('<ctrl>')
            if event.state & 0x0008 or event.state & 0x0020: parts.append('<alt>')
            if event.state & 0x0001: parts.append('<shift>')
            if event.state & 0x0040: parts.append('<cmd>')

            keysym = event.keysym
            if keysym in modifiers:
                mod_str = modifiers[keysym]
                if mod_str not in parts: parts.append(mod_str)
                hotkey_var.set("+".join(parts))
            else:
                key_name = keysym.lower()
                if len(key_name) > 1: key_name = f"<{key_name}>"
                if key_name not in parts: parts.append(key_name)
                hotkey_var.set("+".join(parts))
            return "break"

        hotkey_entry.bind("<KeyPress>", on_key_press)
        ctk.CTkLabel(scroll_frame, text="Click above and press keys to set hotkey", font=(AppConfig.FONT_FAMILY, 9), text_color=AppConfig.TEXT_COLOR_SECONDARY).pack()
        
        hotkey_enabled_var = ctk.BooleanVar(value=self.hotkey_enabled)
        hotkey_cb = ctk.CTkCheckBox(scroll_frame, text="Enable Hotkey", variable=hotkey_enabled_var)
        hotkey_cb.pack(pady=5)

        # Language
        ctk.CTkLabel(scroll_frame, text="Language (ISO code):").pack(pady=(10, 0))
        lang_var = ctk.StringVar(value=self.whisper_language if self.whisper_language else "auto")
        lang_entry = ctk.CTkEntry(scroll_frame, textvariable=lang_var)
        lang_entry.pack(pady=5)
        ctk.CTkLabel(scroll_frame, text="(e.g., 'en', 'es', 'fr' or 'auto')", font=(AppConfig.FONT_FAMILY, 9), text_color=AppConfig.TEXT_COLOR_SECONDARY).pack()

        def save_settings():
            # Check if compute settings changed to trigger model reload
            new_device = device_var.get()
            new_compute = compute_var.get()
            needs_model_reload = (self.whisper_device != new_device or 
                                self.whisper_compute_type != new_compute)

            selected_name = input_device_var.get()
            if selected_name == "Default":
                self.selected_input_device_index = None
            else:
                for d in input_devices:
                    if d['name'] == selected_name:
                        self.selected_input_device_index = d['index']
                        break

            self.whisper_device = new_device
            self.whisper_compute_type = new_compute
            self.global_hotkey = hotkey_var.get().strip()
            self.hotkey_enabled = hotkey_enabled_var.get()
            val = lang_var.get().strip().lower()
            self.whisper_language = None if val == "auto" else val
            
            self.save_config()
            self.setup_hotkey_listener()
            
            if needs_model_reload:
                self.status_label.configure(text="Reloading Model...", text_color=AppConfig.WARNING_COLOR)
                self.record_btn.configure(state="disabled")
                self.import_btn.configure(state="disabled")
                threading.Thread(target=self._load_whisper_model, daemon=True).start()
            
            self.status_label.configure(text="Changes Saved!", text_color=AppConfig.SUCCESS_COLOR)
            self.after(3000, lambda: self.status_label.configure(text="Ready to Listen", text_color=AppConfig.TEXT_COLOR_SECONDARY))
            settings_win.destroy()

        def restore_defaults():
            if os.path.exists(self.config_file):
                try:
                    os.remove(self.config_file)
                except Exception as e:
                    print(f"Error deleting config file: {e}")
            
            # Reload config defaults from hardcoded values
            self.load_config()
            self.setup_hotkey_listener()
            
            # Reload model to reflect default compute settings
            self.status_label.configure(text="Restoring Defaults & Reloading...", text_color=AppConfig.WARNING_COLOR)
            self.record_btn.configure(state="disabled")
            self.import_btn.configure(state="disabled")
            threading.Thread(target=self._load_whisper_model, daemon=True).start()
            
            self.after(1000, lambda: self.status_label.configure(text="Defaults Restored!", text_color=AppConfig.SUCCESS_COLOR))
            settings_win.destroy()

        save_btn = ctk.CTkButton(scroll_frame, text="SAVE CHANGES", command=save_settings, fg_color=AppConfig.ACCENT_COLOR)
        save_btn.pack(pady=(20, 10))

        reset_btn = ctk.CTkButton(scroll_frame, text="RESTORE DEFAULTS", command=restore_defaults, fg_color=AppConfig.STOP_BTN_COLOR)
        reset_btn.pack(pady=5)

        ctk.CTkLabel(scroll_frame, 
                     text="To truly reset every setting, close the app and delete the\n'config.json' file in the application folder.", 
                     font=(AppConfig.FONT_FAMILY, 9), 
                     text_color=AppConfig.TEXT_COLOR_SECONDARY).pack(pady=(0, 10))

    def import_audio(self):
        if self.model is None:
            return
        file_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav *.m4a")])
        if file_path:
            threading.Thread(target=self.process_audio, args=(file_path,)).start()

    def type_out(self, text):
        if not text: return
        time.sleep(0.5)
        self.keyboard.type(text)

if __name__ == "__main__":
    app = SpeechWidget()
    app.mainloop()
