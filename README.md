# sOuLSPEECH: Whisper Offline STT Widget

A lightweight, floating desktop widget for real-time Speech-to-Text (STT) transcription, powered by `faster-whisper`. This application allows users to transcribe spoken audio directly into any focused text field, import audio files for transcription, and operates entirely offline after initial setup.

## ✨ Features

*   **Real-time Transcription:** Convert spoken words from your microphone into text as you speak.
*   **Auto-Typing:** Automatically types the transcribed text into the currently active text input field (e.g., Notepad, browser, Word).
*   **Audio File Import:** Transcribe existing audio files (`.mp3`, `.wav`, `.m4a`) directly from your computer.
*   **Fully Offline:** After the model is downloaded and bundled, the application functions without an internet connection.
*   **Floating Widget UI:** A frameless, always-on-top, and draggable interface built with `CustomTkinter` for a modern look.
*   **Optimized Performance:** Uses `faster-whisper` for efficient transcription on CPU.

---

## 🚀 For End Users: Download & Run `sOuLSPEECH.exe`

To use sOuLSPEECH on your Windows system, follow these steps.

1.  **Download the Application:**
    *   Get the latest `sOuLSPEECH.exe` from [**YOUR RELEASE PAGE/DIST FOLDER LINK HERE**].
    *   Save it to a location on your computer (e.g., your Desktop or a dedicated folder).

2.  **Essential System Dependencies (Mandatory!):**

    *   **FFmpeg (Crucial for Audio Processing):**
        This tool is essential for sOuLSPEECH to process any audio (microphone or imported files). It is **NOT** bundled with the `.exe` and must be installed on your system.
        1.  **Download FFmpeg:** Go to [gyan.dev/ffmpeg/builds/](https://www.gyan.dev/ffmpeg/builds/) and download a `release full` build (e.g., `ffmpeg-N.N-full_build.zip`).
        2.  **Extract:** Unzip the downloaded file (e.g., to `C:\ffmpeg`).
        3.  **Add to System PATH:** This is important!
            *   Search for "Environment Variables" in your Windows search bar and select "Edit the system environment variables".
            *   Click "Environment Variables..."
            *   Under "System variables", find and select the `Path` variable, then click "Edit...".
            *   Click "New" and add the path to the `bin` folder *inside* your FFmpeg directory (e.g., `C:\ffmpeg\bin`).
            *   Click "OK" on all windows to save the changes.
            *   **Restart your computer** for the changes to take full effect.
        *   **Verification:** Open a new Command Prompt (CMD) or PowerShell window and type `ffmpeg -version`. If you see version information, FFmpeg is correctly installed.

    *   **Microsoft Visual C++ Redistributable (Highly Recommended):**
        Many applications built with C++ (which `faster-whisper` relies on) require these runtime libraries. If you don't have them, the `.exe` might fail to start.
        *   Download and install the latest "Visual Studio 2015, 2017, 2019, and 2022" redistributable (both `x86` and `x64` versions are safe to install) from [Microsoft's website](https://learn.microsoft.com/en-us/cpp/windows/latest-supported-visual-cpp-redistributable).

3.  **Run sOuLSPEECH:**
    *   Simply **double-click** the `sOuLSPEECH.exe` file.
    *   A small, frameless widget window should appear on your screen.

---

## 📝 Usage

1.  **Launch the Widget:** Double-click the `sOuLSPEECH.exe` file.
2.  **Reposition:** Click and drag the widget to move it anywhere on your screen.
3.  **Start Real-time Transcription:**
    *   Click the "START RECORDING" button. The button will change to "STOP", and the status will indicate "Recording...".
    *   Click into any text field (e.g., in Notepad, a web browser, or Word) where you want the transcribed text to appear.
    *   Begin speaking clearly into your microphone.
    *   Click "STOP" to finish recording and process the audio. The transcribed text will be typed out automatically.
4.  **Import Audio File:**
    *   Click the "IMPORT" button.
    *   Select an `.mp3`, `.wav`, or `.m4a` file from your computer.
    *   The application will process the file, and automatically type the full transcription into the last focused text field.
5.  **Copy Text:**
    *   The transcribed text will appear in the widget's text area. Click "COPY TEXT" to copy it to your clipboard.
6.  **Minimize/Maximize:**
    *   Click the "—" button in the title bar to minimize the widget to a small floating icon.
    *   Click the "✕" button to close the application.

---

## ⚠️ Troubleshooting (For End Users)

*   **"sOuLSPEECH.exe is not a valid Win32 application" / Missing DLL errors:**
    *   This often points to a missing **Microsoft Visual C++ Redistributable**. Please install the latest versions as described in **Step 2.2** above.
*   **"ffmpeg not found" / "Audio processing failed" errors:**
    *   This is almost always due to **FFmpeg not being correctly installed or added to your system's PATH**. Carefully re-follow **Step 2.1** and remember to **restart your computer** after modifying the PATH.
*   **Application starts but doesn't record / "Microphone error":**
    *   Check your Windows privacy settings. Go to `Settings > Privacy & security > Microphone` and ensure "Microphone access" is turned on and "Let desktop apps access your microphone" is also enabled.
*   **Transcribed text isn't typed into other applications:**
    *   Your antivirus or security software might be blocking `sOuLSPEECH.exe` from simulating keyboard input (as `pynput` does). You may need to add an exception for `sOuLSPEECH.exe` in your security software.
*   **Application is slow or freezes:**
    *   Transcribing audio, especially in real-time, is CPU-intensive. Close other demanding applications. Ensure your computer meets basic requirements (e.g., modern dual-core CPU, 4GB+ RAM).
*   **`sOuLSPEECH.exe` is quarantined by antivirus:**
    *   As mentioned for auto-typing, `pynput` can sometimes trigger false positives. You might need to manually whitelist the application with your antivirus.

---

## 🛠️ For Developers: Setup, Building, & Contributing

This section is for those who want to set up the project locally, modify the code, or build the executable from source.

### 1. Prerequisites (For Development)

*   **Python 3.8+**: Download from [python.org](https://www.python.org/downloads/).
*   **FFmpeg**: (Same as for End Users) Essential for audio processing. Follow **Step 2.1** above.
*   **C++ Compiler (for Nuitka/PyInstaller builds)**: If you plan to build the `.exe`, Nuitka/PyInstaller requires a C++ compiler. The easiest way is to install [Visual Studio Community Edition](https://visualstudio.microsoft.com/downloads/) and select the "Desktop development with C++" workload during installation.

### 2. Setup & Installation (Development Environment)

1.  **Clone the Repository:**
    ```bash
    git clone <your-repo-url>
    cd Speech-To-Text-WHISPER-ANYWHERE # Or your project folder name
    ```

2.  **Create and Activate a Virtual Environment:**
    ```bash
    python -m venv venv
    # On Windows:
    .\venv\Scripts\activate
    # On macOS/Linux:
    source venv/bin/activate
    ```

3.  **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4.  **Download Whisper Model Files (For Offline Bundling):**
    To embed the model for offline functionality, you need to manually download the `faster-whisper` model weights.
    *   Go to a Hugging Face repository for `faster-whisper` models, e.g., [Systran/faster-whisper-base](https://huggingface.co/Systran/faster-whisper-base/tree/main).
    *   Download the following files (or corresponding files for a different model size like `tiny`):
        *   `model.bin`
        *   `config.json`
        *   `vocabulary.txt`
        *   `tokenizer.json`
    *   Create a new folder named `model_files` in your project's root directory (next to `app.py`).
    *   Place all the downloaded model files into the `model_files` folder.
    *   **Note on Model Size:** The `base` model is a good balance of accuracy and size (~73MB). Larger models like `large-v3` offer better accuracy but significantly increase the `.exe` file size, making the download and build process longer.

### 3. Running the Application (From Python Source)

With your virtual environment activated and model files in place:

```bash
python app.py
```
A small, frameless widget window named "sOuLSPEECH" should appear on your screen.

### 4. Building the Executable (`sOuLSPEECH.exe`) for Distribution

**Recommendation:** For `faster-whisper` projects, **Nuitka** often provides better performance and smaller binaries than PyInstaller. However, both options are provided below.

#### Option A: Using PyInstaller (Current Method)

1.  **Install PyInstaller:** (If not already in `requirements.txt`)
    ```bash
    pip install pyinstaller
    ```

2.  **Run the PyInstaller Build Command:**
    Navigate to your project's root directory in the terminal (with the virtual environment activated).
    ```powershell
    pyinstaller --name "sOuLSPEECH" --onefile --windowed --icon="icon.ico" `
    --add-data "model_files;model_files" `
    --add-data "icon.png;." `
    --add-data "icon.ico;." `
    app.py
    ```
    *(Note: Using `` ` `` for line continuation in PowerShell. For Windows CMD, use `^`)*

3.  **Locate the Executable:**
    After a successful build (which may take several minutes depending on your system and model size), your `sOuLSPEECH.exe` will be found in the `dist` directory.

#### Option B: Using Nuitka (Recommended for Performance)

1.  **Install Nuitka:** (If not already in `requirements.txt`)
    ```bash
    pip install nuitka
    ```

2.  **Run the Nuitka Build Command:**
    ```powershell
    python -m nuitka --standalone --onefile --windows-disable-console --output-filename="sOuLSPEECH" ^
    --include-data-dir=model_files=model_files ^
    --include-data-file=icon.png=icon.png ^
    --include-data-file=icon.ico=icon.ico ^
    --windows-icon-template=icon.ico ^
    --plugin-enable=tk-inter ^
    app.py
    ```
    *(Note: Using `^` for line continuation in Windows CMD/PowerShell for Nuitka command)*
    *   `--output-filename="sOuLSPEECH"`: Sets the name of the output `.exe`.
    *   `--windows-icon-template=icon.ico`: Sets the icon of the `.exe` file.

3.  **Locate the Executable:**
    After a successful build (which can take significantly longer than PyInstaller, but often results in a faster `.exe`), your `sOuLSPEECH.exe` will be found in the current directory or a `build` subdirectory.

---

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for details.