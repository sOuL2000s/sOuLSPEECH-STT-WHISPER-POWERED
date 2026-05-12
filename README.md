# Whisper Offline STT Widget

A lightweight, floating desktop widget for real-time Speech-to-Text (STT) transcription, powered by `faster-whisper`. This application allows users to transcribe spoken audio directly into any focused text field, import audio files for transcription, and operates entirely offline after initial setup.

## ✨ Features

*   **Real-time Transcription:** Convert spoken words from your microphone into text as you speak.
*   **Auto-Typing:** Automatically types the transcribed text into the currently active text input field (e.g., Notepad, browser, Word).
*   **Audio File Import:** Transcribe existing audio files (`.mp3`, `.wav`, `.m4a`) directly from your computer.
*   **Fully Offline:** After the model is downloaded and bundled, the application functions without an internet connection.
*   **Floating Widget UI:** A frameless, always-on-top, and draggable interface built with `CustomTkinter` for a modern look.
*   **Optimized Performance:** Uses `faster-whisper` for efficient transcription on CPU.

## 🛠️ Prerequisites

Before you begin, ensure you have the following installed on your Windows PC:

1.  **Python 3.8+**: Download from [python.org](https://www.python.org/downloads/).
2.  **FFmpeg**: Essential for audio processing.
    *   Download a static build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/).
    *   Extract the archive and add the `bin` folder (e.g., `C:\ffmpeg\bin`) to your System Environment Variables `PATH`.
3.  **C++ Compiler (for Nuitka builds)**: If you plan to build the `.exe`, Nuitka requires a C++ compiler. The easiest way is to install [Visual Studio Community Edition](https://visualstudio.microsoft.com/downloads/) and select the "Desktop development with C++" workload during installation.

## 🚀 Setup & Installation (Development)

1.  **Clone the Repository (or create project files):**
    ```bash
    # If you have a Git repo
    git clone <your-repo-url>
    cd <your-project-folder>
    ```
    If you're starting from scratch, create a project folder and place the `app.py` file inside it.

2.  **Create a Virtual Environment:**
    ```bash
    python -m venv venv
    ```

3.  **Activate the Virtual Environment:**
    *   **Windows:**
        ```bash
        .\venv\Scripts\activate
        ```
    *   **macOS/Linux:**
        ```bash
        source venv/bin/activate
        ```

4.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

5.  **Download Whisper Model Files:**
    To enable offline functionality, you need to manually download the `faster-whisper` model weights.
    *   Go to a Hugging Face repository for `faster-whisper` models, e.g., [Systran/faster-whisper-base](https://huggingface.co/Systran/faster-whisper-base/tree/main).
    *   Download the following files:
        *   `model.bin`
        *   `config.json`
        *   `vocabulary.txt`
        *   `tokenizer.json`
    *   Create a new folder named `model_files` in your project's root directory (next to `app.py`).
    *   Place all the downloaded model files into the `model_files` folder.
    *   **Note on Model Size:** The `base` model is a good balance of accuracy and size (~73MB). Larger models like `large-v3` offer better accuracy but significantly increase the `.exe` file size.

## ▶️ Running the Application (Development)

With your virtual environment activated and model files in place:

```bash
python app.py
```
A small, frameless widget window should appear on your screen.

## 📦 Building the Executable (`.exe`) for Distribution

To create a single, standalone `.exe` file that users can run without any Python installation:

1.  **Install Nuitka (if not already installed):**
    ```bash
    pip install nuitka
    ```

2.  **Run the Nuitka Build Command:**
    Navigate to your project's root directory in the terminal (with the virtual environment activated).
    ```bash
    python -m nuitka --standalone --onefile --windows-disable-console --include-data-dir=model_files=model_files --plugin-enable=tk-inter app.py
    ```
    *   `--standalone`: Creates a self-contained application.
    *   `--onefile`: Packages everything into a single `.exe`.
    *   `--windows-disable-console`: Prevents the console window from appearing when the `.exe` is run.
    *   `--include-data-dir=model_files=model_files`: **Crucially**, this embeds your `model_files` directory and its contents directly into the `.exe`, ensuring offline operation.
    *   `--plugin-enable=tk-inter`: Enables necessary plugins for Tkinter (and CustomTkinter) to work correctly.
    *   `app.py`: Your main application file.

3.  **Locate the Executable:**
    After a successful build (which may take several minutes depending on your system and model size), your `app.exe` (or similar name) will be found in the current directory or a `build` subdirectory.

## 📝 Usage

1.  **Launch the Widget:** Double-click the `app.py` (development) or `app.exe` (bundled) file.
2.  **Reposition:** Click and drag the widget to move it anywhere on your screen.
3.  **Start Real-time Transcription:**
    *   Click the "Start Recording" button.
    *   Click into any text field where you want the transcribed text to appear.
    *   Begin speaking into your microphone.
    *   Click "STOP" to finish recording and process the audio. The transcribed text will be typed out.
4.  **Import Audio File:**
    *   Click the "Import File" button.
    *   Select an `.mp3`, `.wav`, or `.m4a` file from your computer.
    *   The application will process the file and automatically type the full transcription into the last focused text field.

## ⚠️ Troubleshooting

*   **FFmpeg Not Found:** If you encounter errors related to FFmpeg, ensure it's installed correctly and its `bin` directory is added to your system's `PATH` environment variable. Restart your terminal/IDE after adding it.
*   **Microphone Issues:** Check your system's privacy settings to ensure your microphone is accessible to applications.
*   **`pynput` Permissions:** While less common on Windows, ensure no security software is blocking `pynput` from simulating keyboard input.

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for details.
