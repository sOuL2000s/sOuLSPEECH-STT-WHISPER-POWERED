import os
import sys
import threading
import wave
import pyaudio
import customtkinter as ctk
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
        self.title("Whisper Widget")
        self.geometry("300x150+100+100")
        self.overrideredirect(True)      # Frameless
        self.attributes("-topmost", True) # Always on top
        self.attributes("-alpha", 0.9)   # Slightly transparent
        self.configure(fg_color="#1e1e1e")

        # --- Variables ---
        self.is_recording = False
        self.keyboard = Controller()
        self.audio_frames = []
        self.stream = None
        self.p = pyaudio.PyAudio()
        
        # Load Model Offline
        model_path = get_resource_path("model_files")
        self.model = WhisperModel(model_path, device="cpu", compute_type="int8")

        # --- UI Elements ---
        self.label = ctk.CTkLabel(self, text="Whisper Offline STT", font=("Arial", 12, "bold"))
        self.label.pack(pady=5)

        self.status_label = ctk.CTkLabel(self, text="Ready", text_color="gray")
        self.status_label.pack()

        self.record_btn = ctk.CTkButton(self, text="Start Recording", command=self.toggle_record, 
                                        fg_color="#2ecc71", hover_color="#27ae60", width=120)
        self.record_btn.pack(pady=5)

        self.import_btn = ctk.CTkButton(self, text="Import File", command=self.import_audio, 
                                        fg_color="#3498db", width=120)
        self.import_btn.pack(pady=5)

        # --- Drag Logic ---
        self.bind("<ButtonPress-1>", self.start_move)
        self.bind("<B1-Motion>", self.do_move)

    def start_move(self, event):
        self.x = event.x
        self.y = event.y

    def do_move(self, event):
        deltax = event.x - self.x
        deltay = event.y - self.y
        self.geometry(f"+{self.winfo_x() + deltax}+{self.winfo_y() + deltay}")

    # --- Core Logic ---
    def toggle_record(self):
        if not self.is_recording:
            self.is_recording = True
            self.record_btn.configure(text="STOP", fg_color="#e74c3c")
            self.status_label.configure(text="Listening...", text_color="#e74c3c")
            threading.Thread(target=self.record_audio).start()
        else:
            self.is_recording = False
            self.record_btn.configure(text="Processing...", state="disabled")

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
        
        # Save temp file
        temp_file = "temp_cache.wav"
        wf = wave.open(temp_file, 'wb')
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(self.p.get_sample_size(FORMAT))
        wf.setframerate(RATE)
        wf.writeframes(b''.join(self.audio_frames))
        wf.close()

        self.process_audio(temp_file)

    def process_audio(self, file_path):
        self.status_label.configure(text="Transcribing...", text_color="yellow")
        
        segments, _ = self.model.transcribe(file_path, beam_size=5)
        full_text = ""
        for segment in segments:
            full_text += segment.text + " "

        self.type_out(full_text.strip())
        
        # UI Cleanup
        self.record_btn.configure(text="Start Recording", state="normal", fg_color="#2ecc71")
        self.status_label.configure(text="Ready", text_color="gray")

    def import_audio(self):
        file_path = filedialog.askopenfilename(filetypes=[("Audio Files", "*.mp3 *.wav *.m4a")])
        if file_path:
            threading.Thread(target=self.process_audio, args=(file_path,)).start()

    def type_out(self, text):
        
        if not text: return
        # Brief delay to allow user to click their target text field
        time.sleep(0.5)
        self.keyboard.type(text)

if __name__ == "__main__":
    app = SpeechWidget()
    app.mainloop()
