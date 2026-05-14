import os
import sys
import threading
import wave
import pyaudio
import json
import subprocess
import math
import struct
import tkinter as tk
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
    PRIMARY_BG = ("#f0f0f0", "#121212")
    TITLE_BAR_BG = ("#e0e0e0", "#1f1f1f")
    TEXT_AREA_BG = ("#ffffff", "#1e1e1e")
    SECONDARY_BG = "#34495e"
    BORDER_COLOR = ("#cccccc", "#333333")
    
    # Accent Color Presets
    ACCENT_PRESETS = {
        "Blue": {"main": "#3498db", "hover": "#2980b9"},
        "Green": {"main": "#2ecc71", "hover": "#27ae60"},
        "Orange": {"main": "#e67e22", "hover": "#d35400"},
        "Purple": {"main": "#9b59b6", "hover": "#8e44ad"},
    }
    
    DEFAULT_ACCENT = "Blue"
    RECORD_BTN_COLOR = "#2ecc71"
    RECORD_BTN_HOVER = "#27ae60"
    STOP_BTN_COLOR = "#e74c3c"
    STOP_BTN_HOVER = "#c0392b"
    PROGRESS_BG = ("#d0d0d0", "#2c2c2c")
    UI_GRAY = "#555555"
    UI_GRAY_HOVER = "#666666"
    SECONDARY_HOVER = "#2c3e50"
    
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
        self.is_animating = False
        self.is_transcribing_live = False
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
        self.attributes("-topmost", self.always_on_top) 
        self.attributes("-alpha", self.window_opacity)   
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
        
        self.tooltip_window = None
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
                    self.auto_copy = config.get('auto_copy', False)
                    self.auto_type = config.get('auto_type', False)
                    self.window_opacity = config.get('window_opacity', 0.95)
                    self.always_on_top = config.get('always_on_top', True)
                    self.appearance_mode = config.get('appearance_mode', "Dark")
                    self.accent_color_name = config.get('accent_color', AppConfig.DEFAULT_ACCENT)
                    self.history = config.get('history', [])
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
            self.auto_copy = False
            self.auto_type = False
            self.window_opacity = 0.95
            self.always_on_top = True
            self.appearance_mode = "Dark"
            self.accent_color_name = AppConfig.DEFAULT_ACCENT
            self.history = []

        # Apply theme and resolve current accent colors
        preset = AppConfig.ACCENT_PRESETS.get(self.accent_color_name, AppConfig.ACCENT_PRESETS[AppConfig.DEFAULT_ACCENT])
        self.accent_color = preset["main"]
        self.accent_hover = preset["hover"]
        ctk.set_appearance_mode(self.appearance_mode)

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
            'hotkey_enabled': self.hotkey_enabled,
            'auto_copy': self.auto_copy,
            'auto_type': self.auto_type,
            'window_opacity': self.window_opacity,
            'always_on_top': self.always_on_top,
            'appearance_mode': self.appearance_mode,
            'accent_color': self.accent_color_name,
            'history': self.history
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

        # Main Outer Container with rounded corners for expanded island look
        outer_frame = ctk.CTkFrame(self, fg_color=AppConfig.PRIMARY_BG, corner_radius=20, border_width=1, border_color=AppConfig.BORDER_COLOR)
        outer_frame.pack(expand=True, fill="both", padx=2, pady=2)

        # Custom Title Bar
        title_bar = ctk.CTkFrame(outer_frame, fg_color=AppConfig.TITLE_BAR_BG, height=35, corner_radius=0)
        title_bar.pack(fill="x", side="top")
        
        title_label = ctk.CTkLabel(title_bar, text="sOuLSPEECH", font=(AppConfig.FONT_FAMILY, AppConfig.TITLE_FONT_SIZE, "bold"), text_color=self.accent_color)
        title_label.pack(side="left", padx=10)

        close_btn = ctk.CTkButton(title_bar, text="✕", width=35, height=35, fg_color="transparent", 
                                  hover_color=AppConfig.STOP_BTN_COLOR, corner_radius=0, command=self.quit)
        close_btn.pack(side="right")

        settings_btn = ctk.CTkButton(title_bar, text="⚙", width=35, height=35, fg_color="transparent", 
                                     hover_color=AppConfig.SECONDARY_BG, corner_radius=0, command=self.open_settings)
        settings_btn.pack(side="right")

        history_btn = ctk.CTkButton(title_bar, text="📜", width=35, height=35, fg_color="transparent", 
                                    hover_color=AppConfig.SECONDARY_BG, corner_radius=0, command=self.open_history)
        history_btn.pack(side="right")

        min_btn = ctk.CTkButton(title_bar, text="—", width=35, height=35, fg_color="transparent", 
                                hover_color=AppConfig.SECONDARY_BG, corner_radius=0, command=self.toggle_minimize)
        min_btn.pack(side="right")

        # Main Content
        main_frame = ctk.CTkFrame(outer_frame, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=15, pady=10)

        initial_status = "Ready to Listen" if self.model else "Checking Model Files..."
        initial_color = AppConfig.TEXT_COLOR_SECONDARY if self.model else AppConfig.WARNING_COLOR
        initial_state = "normal" if self.model else "disabled"

        # Status and Level Indicator container
        status_container = ctk.CTkFrame(main_frame, fg_color="transparent")
        status_container.pack(fill="x", pady=(0, 5))

        self.status_label = ctk.CTkLabel(status_container, text=initial_status, font=(AppConfig.FONT_FAMILY, AppConfig.STATUS_FONT_SIZE), text_color=initial_color)
        self.status_label.pack(side="left", expand=True, padx=(20, 0))

        self.level_indicator = ctk.CTkProgressBar(status_container, width=60, height=4, fg_color=AppConfig.PROGRESS_BG, progress_color=AppConfig.RECORD_BTN_COLOR)
        self.level_indicator.set(0)
        self.level_indicator.pack(side="right", padx=(0, 10))

        self.progress_bar = ctk.CTkProgressBar(main_frame, height=8, fg_color=AppConfig.PROGRESS_BG, progress_color=self.accent_color)
        self.progress_bar.set(0)
        if not self.model:
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
        self.progress_bar.pack(fill="x", pady=5)

        self.text_area = ctk.CTkTextbox(main_frame, font=(AppConfig.FONT_FAMILY, AppConfig.TEXT_FONT_SIZE), fg_color=AppConfig.TEXT_AREA_BG, border_width=1, border_color=AppConfig.BORDER_COLOR)
        self.text_area.pack(expand=True, fill="both", pady=10)

        btn_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_row.pack(fill="x")

        self.record_btn = ctk.CTkButton(btn_row, text="⏺ RECORD", command=self.toggle_record, 
                                        fg_color=AppConfig.RECORD_BTN_COLOR, hover_color=AppConfig.RECORD_BTN_HOVER, 
                                        font=(AppConfig.FONT_FAMILY, AppConfig.TEXT_FONT_SIZE, "bold"), height=45, state=initial_state)
        self.record_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.import_btn = ctk.CTkButton(btn_row, text="📁", command=self.import_audio, 
                                        fg_color=AppConfig.SECONDARY_BG, width=50, height=45, state=initial_state)
        self.import_btn.pack(side="right")

        # Action Button Row
        action_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        action_row.pack(fill="x", pady=(10, 0))

        copy_btn = ctk.CTkButton(action_row, text="📋 COPY", command=self.copy_to_clipboard, 
                                 fg_color=self.accent_color, hover_color=self.accent_hover, height=35)
        copy_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        clear_btn = ctk.CTkButton(action_row, text="🗑️ CLEAR", command=self.clear_text_area,
                                  fg_color=AppConfig.UI_GRAY, height=35)
        clear_btn.pack(side="right", expand=True, fill="x")

    def setup_minimized_ui(self):
        # Pill shape for Dynamic Island UI
        width, height = 200, 45
        self.geometry(f"{width}x{height}")
        
        pill_frame = ctk.CTkFrame(self, fg_color=AppConfig.TITLE_BAR_BG, corner_radius=22, border_width=1, border_color=self.accent_color)
        pill_frame.pack(expand=True, fill="both", padx=2, pady=2)
        
        # Indicator on left
        status_color = AppConfig.RECORD_BTN_COLOR if self.is_recording else self.accent_color
        self.island_icon = ctk.CTkLabel(pill_frame, text="●" if self.is_recording else "S", 
                                        font=(AppConfig.FONT_FAMILY, 18, "bold"), 
                                        text_color=status_color, width=40)
        self.island_icon.pack(side="left", padx=(10, 5))
        
        # Status Text in middle
        display_text = "Recording..." if self.is_recording else "sOuLSPEECH"
        self.island_label = ctk.CTkLabel(pill_frame, text=display_text, 
                                         font=(AppConfig.FONT_FAMILY, 12, "bold"), 
                                         text_color="white")
        self.island_label.pack(side="left", expand=True)

        # Expand button on right
        expand_btn = ctk.CTkButton(pill_frame, text="↗", width=30, height=30, 
                                   fg_color="transparent", hover_color=AppConfig.SECONDARY_BG,
                                   corner_radius=15, command=self.toggle_minimize)
        expand_btn.pack(side="right", padx=5)

        # Bindings for the pill frame to allow dragging and interaction
        for widget in [pill_frame, self.island_icon, self.island_label]:
            widget.bind("<Button-1>", self.start_move)
            widget.bind("<B1-Motion>", self.do_move)
            widget.bind("<Button-3>", self.show_context_menu)
            widget.bind("<Enter>", self.show_tooltip)
            widget.bind("<Leave>", self.hide_tooltip)

    def show_tooltip(self, event=None):
        if self.tooltip_window or not self.is_minimized:
            return
            
        x = self.winfo_x() + 70
        y = self.winfo_y() + 10
        
        self.tooltip_window = tw = tk.Toplevel(self)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tw.attributes("-topmost", True)
        
        hotkey_str = self.global_hotkey.replace("<", "").replace(">", "").upper()
        text = f"sOuLSPEECH\nClick: Expand\nHotkey: {hotkey_str}"
        
        label = tk.Label(tw, text=text, justify='left',
                         background="#2c3e50", foreground="white",
                         relief='flat', borderwidth=0,
                         font=(AppConfig.FONT_FAMILY, 9), padx=8, pady=5)
        label.pack(ipadx=1)

    def hide_tooltip(self, event=None):
        if self.tooltip_window:
            self.tooltip_window.destroy()
            self.tooltip_window = None

    def show_context_menu(self, event):
        menu = tk.Menu(self, tearoff=0, bg="#1e1e1e", fg="white", activebackground=self.accent_color, activeforeground="white", borderwidth=0)
        
        record_label = "Stop Recording" if self.is_recording else "Start Recording"
        menu.add_command(label=record_label, command=self.toggle_record)
        menu.add_separator()
        menu.add_command(label="Expand Window", command=self.toggle_minimize)
        menu.add_command(label="Settings", command=self.open_settings)
        menu.add_separator()
        menu.add_command(label="Exit", command=self.quit)
        
        try:
            menu.tk_popup(event.x_root, event.y_root)
        finally:
            menu.grab_release()

    def toggle_minimize(self):
        if self.is_animating:
            return
        
        self.hide_tooltip()
        self.is_animating = True
        
        # Determine target dimensions for smooth transition
        if not self.is_minimized:
            # Shrinking to Pill
            self.last_expanded_geo = self.geometry()
            target_w, target_h = 200, 45
        else:
            # Expanding to Window
            parts = self.last_expanded_geo.split('+')
            size_part = parts[0].split('x')
            target_w, target_h = int(size_part[0]), int(size_part[1])

        self.animate_transition(target_w, target_h)

    def animate_transition(self, target_w, target_h, steps=12):
        # Current geometry components
        parts = self.geometry().split('+')
        curr_size = parts[0].split('x')
        curr_w, curr_h = int(curr_size[0]), int(curr_size[1])
        curr_x, curr_y = int(parts[1]), int(parts[2])

        dw = (target_w - curr_w) / steps
        dh = (target_h - curr_h) / steps
        
        def step(i):
            if i <= steps:
                new_w = int(curr_w + dw * i)
                new_h = int(curr_h + dh * i)
                # Keep transition centered relative to previous position
                new_x = curr_x + (curr_w - new_w) // 2
                new_y = curr_y + (curr_h - new_h) // 2
                
                self.geometry(f"{new_w}x{new_h}+{new_x}+{new_y}")
                self.after(8, lambda: step(i + 1))
            else:
                self.is_minimized = not self.is_minimized
                self.setup_ui()
                self.setup_bindings()
                self.is_animating = False

        # Clear existing widgets during animation to prevent layout thrashing
        for widget in self.winfo_children():
            widget.destroy()
        
        step(1)

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
            self.after(0, lambda: self.status_label.configure(text="Loading AI Model (this may take a moment)...", text_color=AppConfig.WARNING_COLOR))
            
            # Provide more granular pseudo-feedback as WhisperModel blocks while loading weights
            self.after(800, lambda: self.status_label.configure(text=f"Loading weights into {self.whisper_device.upper()}..."))
            
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
            self.progress_bar.stop()
            self.progress_bar.configure(mode="determinate")
            self.progress_bar.set(0)

    def _update_ui_on_model_error(self, error_msg):
        if not self.is_minimized:
            self.status_label.configure(text=f"Model Error: {error_msg}", text_color=AppConfig.ERROR_COLOR)
            self.record_btn.configure(state="disabled")
            self.import_btn.configure(state="disabled")
            self.progress_bar.stop()
            self.progress_bar.set(0)

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
            if not self.is_minimized:
                self.record_btn.configure(text="⏹ STOP", fg_color=AppConfig.STOP_BTN_COLOR)
                self.status_label.configure(text="Recording...", text_color=AppConfig.ERROR_COLOR)
                self.progress_bar.set(0)
                self.progress_bar.configure(mode="indeterminate")
                self.progress_bar.start()
            else:
                self.setup_ui() # Refresh Dynamic Island UI
            threading.Thread(target=self.record_audio).start()
        else:
            self.is_recording = False
            if not self.is_minimized:
                self.record_btn.configure(text="⏳ PROCESSING...", state="disabled")
                self.progress_bar.stop()
                self.progress_bar.configure(mode="determinate")
            else:
                self.setup_ui()
            self.update_level_bar(0)

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
            last_live_proc_time = time.time()

            while self.is_recording:
                data = self.stream.read(AppConfig.CHUNK, exception_on_overflow=False)
                self.audio_frames.append(data)
                
                # Audio level calculation (RMS) for visual feedback
                try:
                    count = len(data) // 2
                    shorts = struct.unpack(f"{count}h", data)
                    sum_squares = sum(s*s for s in shorts)
                    rms = math.sqrt(sum_squares / max(1, count)) / 32768.0
                    # Apply gain scaling for visibility (normal speech is usually low RMS)
                    level = min(rms * 12, 1.0)
                    self.after(0, lambda l=level: self.update_level_bar(l))
                except Exception:
                    pass

                # Near real-time transcription trigger (every 2.5 seconds)
                if time.time() - last_live_proc_time > 2.5 and not self.is_transcribing_live:
                    last_live_proc_time = time.time()
                    # Capture current buffer to process in background
                    current_buffer = list(self.audio_frames)
                    threading.Thread(target=self.live_process_audio, args=(current_buffer,), daemon=True).start()

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

    def live_process_audio(self, frames):
        """Processes current audio buffer for real-time feedback."""
        if not frames or self.is_transcribing_live:
            return
        
        self.is_transcribing_live = True
        temp_live_file = "live_cache.wav"
        try:
            wf = wave.open(temp_live_file, 'wb')
            wf.setnchannels(AppConfig.CHANNELS)
            wf.setsampwidth(self.p.get_sample_size(AppConfig.FORMAT))
            wf.setframerate(AppConfig.RATE)
            wf.writeframes(b''.join(frames))
            wf.close()

            # Use faster transcription for live feedback (lower beam size)
            segments, _ = self.model.transcribe(
                temp_live_file, 
                beam_size=1, 
                language=self.whisper_language
            )
            
            full_text = ""
            for segment in segments:
                full_text += segment.text + " "
            
            if full_text.strip() and self.is_recording:
                # Add ellipsis to show it's a partial live result
                display_text = full_text.strip() + "..."
                self.after(0, lambda t=display_text: self.update_text_area(t))

        except Exception as e:
            print(f"Live Transcription Error: {e}")
        finally:
            if os.path.exists(temp_live_file):
                try:
                    os.remove(temp_live_file)
                except:
                    pass
            self.is_transcribing_live = False

    def process_audio(self, file_path):
        self.after(0, lambda: self.status_label.configure(text="Transcribing... 0%", text_color=AppConfig.WARNING_COLOR))
        self.after(0, lambda: self.progress_bar.configure(mode="determinate"))
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
        if not self.is_minimized:
            self.progress_bar.set(val)
            self.status_label.configure(text=f"Transcribing... {int(val*100)}%")
        elif hasattr(self, 'island_label'):
            self.island_label.configure(text=f"Progress: {int(val*100)}%")

    def update_level_bar(self, level):
        if not self.is_minimized and hasattr(self, 'level_indicator'):
            try:
                self.level_indicator.set(level)
            except Exception:
                pass

    def update_text_area(self, text):
        if not self.is_minimized:
            self.text_area.delete("1.0", "end")
            self.text_area.insert("1.0", text)
            self.text_area.see("end")
        elif hasattr(self, 'island_label'):
            snippet = text.strip()
            if len(snippet) > 18: snippet = snippet[:15] + "..."
            self.island_label.configure(text=snippet)

    def finalize_transcription(self, text):
        self._reset_record_button()
        self.status_label.configure(text="Transcription Complete! Copy or Clear.", text_color=AppConfig.SUCCESS_COLOR)
        
        # Add to history
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
        self.history.insert(0, {"timestamp": timestamp, "text": text})
        if len(self.history) > 50: # Limit history size
            self.history = self.history[:50]
        self.save_config()

        # Smoothly complete the bar and reset after a delay
        self.progress_bar.set(1.0)
        self.after(2500, lambda: self.progress_bar.set(0) if not self.is_recording else None)
        self.after(2500, lambda: self.status_label.configure(text="Ready to Listen", text_color=AppConfig.TEXT_COLOR_SECONDARY))
        
        if self.auto_copy:
            self.clipboard_clear()
            self.clipboard_append(text)
            
        if self.auto_type:
            threading.Thread(target=self.type_out, args=(text,), daemon=True).start()

    def _reset_record_button(self):
        if not self.is_minimized:
            self.record_btn.configure(text="⏺ RECORD", state="normal", fg_color=AppConfig.RECORD_BTN_COLOR)
        else:
            self.setup_ui()
        self.update_level_bar(0)

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
        
        hotkey_frame = ctk.CTkFrame(scroll_frame, fg_color="transparent")
        hotkey_frame.pack(pady=5, fill="x", padx=20)
        
        hotkey_var = ctk.StringVar(value=self.global_hotkey)
        hotkey_display = ctk.CTkEntry(hotkey_frame, textvariable=hotkey_var, state="readonly", justify="center")
        hotkey_display.pack(side="left", expand=True, fill="x", padx=(0, 5))
        
        def start_recording_hotkey():
            record_btn.configure(text="Press keys...", state="disabled", fg_color=AppConfig.ORANGE_COLOR)
            hotkey_display.focus_set()
            
            def on_record_key(event):
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
                    return "break"
                else:
                    key_name = keysym.lower()
                    # Mapping for pynput compatibility
                    mapping = {'next': 'page_down', 'prior': 'page_up', 'return': 'enter'}
                    key_name = mapping.get(key_name, key_name)
                    
                    if len(key_name) > 1: key_name = f"<{key_name}>"
                    if key_name not in parts: parts.append(key_name)
                    hotkey_var.set("+".join(parts))
                    
                    record_btn.configure(text="RECORD", state="normal", fg_color=self.accent_color)
                    hotkey_display.unbind("<KeyPress>")
                    # Return focus to scroll frame
                    scroll_frame.focus_set()
                    return "break"

            hotkey_display.bind("<KeyPress>", on_record_key)

        record_btn = ctk.CTkButton(hotkey_frame, text="RECORD", width=80, command=start_recording_hotkey, fg_color=self.accent_color, hover_color=self.accent_hover)
        record_btn.pack(side="right")
        
        ctk.CTkLabel(scroll_frame, text="Click Record then press your key combination", font=(AppConfig.FONT_FAMILY, 9), text_color=AppConfig.TEXT_COLOR_SECONDARY).pack()
        
        hotkey_enabled_var = ctk.BooleanVar(value=self.hotkey_enabled)
        hotkey_cb = ctk.CTkCheckBox(scroll_frame, text="Enable Hotkey", variable=hotkey_enabled_var)
        hotkey_cb.pack(pady=5)

        auto_copy_var = ctk.BooleanVar(value=self.auto_copy)
        auto_copy_cb = ctk.CTkCheckBox(scroll_frame, text="Auto-copy to Clipboard", variable=auto_copy_var)
        auto_copy_cb.pack(pady=5)

        auto_type_var = ctk.BooleanVar(value=self.auto_type)
        auto_type_cb = ctk.CTkCheckBox(scroll_frame, text="Auto-type into Active Window", variable=auto_type_var)
        auto_type_cb.pack(pady=5)

        # Window Appearance & Theming
        ctk.CTkLabel(scroll_frame, text="Appearance & Theming:").pack(pady=(10, 0))
        
        # Mode Toggle
        mode_var = ctk.StringVar(value=self.appearance_mode)
        mode_menu = ctk.CTkOptionMenu(scroll_frame, values=["Dark", "Light"], variable=mode_var,
                                      command=lambda m: ctk.set_appearance_mode(m))
        mode_menu.pack(pady=5)
        
        # Accent Color
        ctk.CTkLabel(scroll_frame, text="Accent Color:").pack(pady=(5, 0))
        accent_var = ctk.StringVar(value=self.accent_color_name)
        accent_menu = ctk.CTkOptionMenu(scroll_frame, values=list(AppConfig.ACCENT_PRESETS.keys()), variable=accent_var)
        accent_menu.pack(pady=5)

        always_on_top_var = ctk.BooleanVar(value=self.always_on_top)
        always_on_top_cb = ctk.CTkCheckBox(scroll_frame, text="Always on Top", variable=always_on_top_var)
        always_on_top_cb.pack(pady=5)

        ctk.CTkLabel(scroll_frame, text="Transparency:").pack(pady=(5, 0))
        opacity_var = ctk.DoubleVar(value=self.window_opacity)
        opacity_slider = ctk.CTkSlider(scroll_frame, from_=0.5, to=1.0, variable=opacity_var)
        opacity_slider.pack(pady=5)

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

            # Update Theming
            self.appearance_mode = mode_var.get()
            self.accent_color_name = accent_var.get()
            preset = AppConfig.ACCENT_PRESETS.get(self.accent_color_name)
            self.accent_color = preset["main"]
            self.accent_hover = preset["hover"]
            
            # Refresh main UI to apply theme/accent colors
            self.after(100, self.setup_ui)

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
            self.auto_copy = auto_copy_var.get()
            self.auto_type = auto_type_var.get()
            self.window_opacity = opacity_var.get()
            self.always_on_top = always_on_top_var.get()
            
            # Apply window settings immediately
            self.attributes("-topmost", self.always_on_top)
            self.attributes("-alpha", self.window_opacity)

            val = lang_var.get().strip().lower()
            self.whisper_language = None if val == "auto" else val
            
            self.save_config()
            self.setup_hotkey_listener()
            
            if needs_model_reload:
                self.status_label.configure(text="Reloading Model...", text_color=AppConfig.WARNING_COLOR)
                self.record_btn.configure(state="disabled")
                self.import_btn.configure(state="disabled")
                self.progress_bar.configure(mode="indeterminate")
                self.progress_bar.start()
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
            
            # Apply restored window settings
            self.attributes("-topmost", self.always_on_top)
            self.attributes("-alpha", self.window_opacity)
            
            # Reload model to reflect default compute settings
            self.status_label.configure(text="Restoring Defaults & Reloading...", text_color=AppConfig.WARNING_COLOR)
            self.record_btn.configure(state="disabled")
            self.import_btn.configure(state="disabled")
            self.progress_bar.configure(mode="indeterminate")
            self.progress_bar.start()
            threading.Thread(target=self._load_whisper_model, daemon=True).start()
            
            # Refresh UI for appearance/accents
            self.setup_ui()
            
            self.after(1000, lambda: self.status_label.configure(text="Defaults Restored!", text_color=AppConfig.SUCCESS_COLOR))
            settings_win.destroy()

        save_btn = ctk.CTkButton(scroll_frame, text="SAVE CHANGES", command=save_settings, fg_color=self.accent_color, hover_color=self.accent_hover)
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

    def open_history(self):
        history_win = ctk.CTkToplevel(self)
        history_win.title("Transcription History")
        history_win.geometry("400x500")
        history_win.attributes("-topmost", True)
        history_win.configure(fg_color=AppConfig.PRIMARY_BG)

        header = ctk.CTkFrame(history_win, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkLabel(header, text="Transcription History", font=(AppConfig.FONT_FAMILY, 16, "bold")).pack(side="left")
        
        def clear_all_history():
            self.history = []
            self.save_config()
            refresh_history()

        clear_btn = ctk.CTkButton(header, text="Clear All", width=80, fg_color=AppConfig.STOP_BTN_COLOR, 
                                  hover_color=AppConfig.STOP_BTN_HOVER, command=clear_all_history)
        clear_btn.pack(side="right")

        scroll_frame = ctk.CTkScrollableFrame(history_win, fg_color="transparent")
        scroll_frame.pack(expand=True, fill="both", padx=10, pady=(0, 10))

        def refresh_history():
            for widget in scroll_frame.winfo_children():
                widget.destroy()
            
            if not self.history:
                ctk.CTkLabel(scroll_frame, text="No history yet.", text_color=AppConfig.TEXT_COLOR_SECONDARY).pack(pady=20)
                return

            for idx, item in enumerate(self.history):
                item_frame = ctk.CTkFrame(scroll_frame, fg_color=AppConfig.TEXT_AREA_BG, border_width=1, border_color=AppConfig.BORDER_COLOR)
                item_frame.pack(fill="x", pady=5, padx=2)
                
                top_row = ctk.CTkFrame(item_frame, fg_color="transparent")
                top_row.pack(fill="x", padx=5, pady=2)
                
                ctk.CTkLabel(top_row, text=item['timestamp'], font=(AppConfig.FONT_FAMILY, 10), text_color=self.accent_color).pack(side="left")
                
                def delete_item(i=idx):
                    self.history.pop(i)
                    self.save_config()
                    refresh_history()
                
                def copy_item(t=item['text']):
                    self.clipboard_clear()
                    self.clipboard_append(t)
                    self.status_label.configure(text="Copied to clipboard!", text_color=AppConfig.SUCCESS_COLOR)
                
                del_btn = ctk.CTkButton(top_row, text="🗑", width=25, height=25, fg_color="transparent", 
                                       text_color=AppConfig.STOP_BTN_COLOR, hover_color=AppConfig.PROGRESS_BG,
                                       command=delete_item)
                del_btn.pack(side="right")
                
                cp_btn = ctk.CTkButton(top_row, text="📋", width=25, height=25, fg_color="transparent", 
                                      text_color=self.accent_color, hover_color=AppConfig.PROGRESS_BG,
                                      command=copy_item)
                cp_btn.pack(side="right")

                txt = ctk.CTkLabel(item_frame, text=item['text'], font=(AppConfig.FONT_FAMILY, 11), 
                                   wraplength=340, justify="left")
                txt.pack(fill="x", padx=10, pady=(0, 5))

        refresh_history()

    def type_out(self, text):
        if not text: return
        time.sleep(0.5)
        self.keyboard.type(text)

if __name__ == "__main__":
    app = SpeechWidget()
    app.mainloop()
