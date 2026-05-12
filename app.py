import os
import sys
import threading
import wave
import pyaudio
import customtkinter as ctk
from PIL import Image
from faster_whisper import WhisperModel
from pynput.keyboard import Controller
import time
from tkinter import filedialog

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
            self.iconbitmap(get_resource_path("icon.ico"))
        except:
            pass
        self.geometry("350x450+100+100")
        self.overrideredirect(True)      
        self.attributes("-topmost", True) 
        self.attributes("-alpha", 0.95)   
        self.configure(fg_color="#121212")

        # --- Variables ---
        self.is_recording = False
        self.is_minimized = False
        self.keyboard = Controller()
        self.audio_frames = []
        self.stream = None
        self.p = pyaudio.PyAudio()
        self.last_expanded_geo = "350x450+100+100"

        # Load Icon
        try:
            icon_path = get_resource_path("icon.png")
            img = Image.open(icon_path)
            self.mic_icon = ctk.CTkImage(light_image=img, dark_image=img, size=(30, 30))
        except Exception:
            self.mic_icon = None
        
        # Load Model Offline
        self.status_label = None # placeholder
        model_path = get_resource_path("model_files")
        # Optimization: lazy load model or load in thread to prevent UI freeze
        self.model = WhisperModel(model_path, device="cpu", compute_type="int8")

        self.setup_ui()
        self.setup_bindings()

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
        self.configure(fg_color="#121212")

        # Custom Title Bar
        title_bar = ctk.CTkFrame(self, fg_color="#1f1f1f", height=35, corner_radius=0)
        title_bar.pack(fill="x", side="top")
        
        title_label = ctk.CTkLabel(title_bar, text="sOuLSPEECH", font=("Segoe UI", 13, "bold"), text_color="#3498db")
        title_label.pack(side="left", padx=10)

        close_btn = ctk.CTkButton(title_bar, text="✕", width=30, height=30, fg_color="transparent", 
                                  hover_color="#e74c3c", command=self.quit)
        close_btn.pack(side="right", padx=2)

        min_btn = ctk.CTkButton(title_bar, text="—", width=30, height=30, fg_color="transparent", 
                                hover_color="#34495e", command=self.toggle_minimize)
        min_btn.pack(side="right", padx=2)

        # Main Content
        main_frame = ctk.CTkFrame(self, fg_color="transparent")
        main_frame.pack(expand=True, fill="both", padx=15, pady=10)

        self.status_label = ctk.CTkLabel(main_frame, text="Ready to Listen", font=("Segoe UI", 11), text_color="#888888")
        self.status_label.pack(pady=(0, 5))

        self.progress_bar = ctk.CTkProgressBar(main_frame, height=8, fg_color="#2c2c2c", progress_color="#3498db")
        self.progress_bar.set(0)
        self.progress_bar.pack(fill="x", pady=5)

        self.text_area = ctk.CTkTextbox(main_frame, font=("Segoe UI", 12), fg_color="#1e1e1e", border_width=1, border_color="#333333")
        self.text_area.pack(expand=True, fill="both", pady=10)

        btn_row = ctk.CTkFrame(main_frame, fg_color="transparent")
        btn_row.pack(fill="x")

        self.record_btn = ctk.CTkButton(btn_row, text="START RECORDING", command=self.toggle_record, 
                                        fg_color="#2ecc71", hover_color="#27ae60", font=("Segoe UI", 12, "bold"), height=40)
        self.record_btn.pack(side="left", expand=True, fill="x", padx=(0, 5))

        self.import_btn = ctk.CTkButton(btn_row, text="IMPORT", command=self.import_audio, 
                                        fg_color="#3498db", width=70, height=40)
        self.import_btn.pack(side="right")

        copy_btn = ctk.CTkButton(main_frame, text="COPY TEXT", command=self.copy_to_clipboard, 
                                 fg_color="#34495e", height=30)
        copy_btn.pack(fill="x", pady=(10, 0))

    def setup_minimized_ui(self):
        # Save current position before shrinking
        self.last_expanded_geo = self.geometry()
        
        # Make circular-ish small floating button
        size = 60
        self.geometry(f"{size}x{size}")
        self.configure(fg_color="#121212")
        
        # Use icon if loaded, otherwise fallback to "S"
        btn_kwargs = {
            "fg_color": "#3498db",
            "hover_color": "#2980b9",
            "corner_radius": size // 2,
            "width": size,
            "height": size,
            "command": self.toggle_minimize
        }
        
        if self.mic_icon:
            self.icon_label = ctk.CTkButton(self, text="", image=self.mic_icon, **btn_kwargs)
        else:
            self.icon_label = ctk.CTkButton(self, text="S", font=("Segoe UI", 24, "bold"), **btn_kwargs)
            
        self.icon_label.pack(expand=True, fill="both")

    def toggle_minimize(self):
        self.is_minimized = not self.is_minimized
        self.setup_ui()
        self.setup_bindings()

    def setup_bindings(self):
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)

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
        self.status_label.configure(text="Copied to clipboard!", text_color="#2ecc71")
        self.after(2000, lambda: self.status_label.configure(text="Ready", text_color="#888888"))

    # --- Core Logic ---
    def toggle_record(self):
        if not self.is_recording:
            self.is_recording = True
            self.record_btn.configure(text="STOP", fg_color="#e74c3c")
            self.status_label.configure(text="Recording...", text_color="#e74c3c")
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
        CHUNK = 1024
        FORMAT = pyaudio.paInt16
        CHANNELS = 1
        RATE = 16000
        
        self.stream = self.p.open(format=FORMAT, channels=CHANNELS, rate=RATE, input=True, frames_per_buffer=CHUNK)
        self.audio_frames = []

        while self.is_recording:
            data = self.stream.read(CHUNK)
            self.audio_frames.append(data)

        self.stream.stop_stream()
        self.stream.close()
        
        temp_file = "temp_cache.wav"
        wf = wave.open(temp_file, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(self.p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(self.audio_frames))
        wf.close()

        self.process_audio(temp_file)

    def process_audio(self, file_path):
        self.status_label.configure(text="Transcribing... 0%", text_color="#f1c40f")
        self.progress_bar.set(0)
        
        try:
            # Get audio duration for progress tracking
            with wave.open(file_path, 'rb') as f:
                duration = f.getnframes() / float(f.getframerate())

            segments, info = self.model.transcribe(file_path, beam_size=5)
            full_text = ""
            
            # Use segment info for progress if available
            for segment in segments:
                full_text += segment.text + " "
                # Update progress based on timestamp
                progress = min(segment.end / duration, 1.0) if duration > 0 else 0.5
                self.after(0, lambda p=progress: self.update_progress(p))
                # Update text box in real-time
                self.after(0, lambda t=full_text: self.update_text_area(t))

            self.after(0, lambda: self.finalize_transcription(full_text.strip()))
        except Exception as e:
            self.after(0, lambda: self.status_label.configure(text=f"Error: {str(e)}", text_color="#e74c3c"))
        
    def update_progress(self, val):
        self.progress_bar.set(val)
        self.status_label.configure(text=f"Transcribing... {int(val*100)}%")

    def update_text_area(self, text):
        self.text_area.delete("1.0", "end")
        self.text_area.insert("1.0", text)
        self.text_area.see("end")

    def finalize_transcription(self, text):
        self.record_btn.configure(text="START RECORDING", state="normal", fg_color="#2ecc71")
        self.status_label.configure(text="Transcription Complete", text_color="#2ecc71")
        self.progress_bar.set(1.0)
        # Optional: Auto-type out as before
        # threading.Thread(target=self.type_out, args=(text,)).start()

    def import_audio(self):
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
