# Auto-HDR

A lightweight Windows utility that automatically toggles HDR on and off when specific games or applications are launched.

## Features
- **Automatic HDR Toggling**: Monitors running processes and switches Windows HDR mode when a configured game starts.
- **Background Operation**: Runs quietly in the system tray.
- **Start with Windows**: Option to automatically start the application on login.
- **Low Overhead**: Uses efficient WMI polling.
- **Customizable**: Easy configuration via `config.json`.

## Installation

1.  **Prerequisites**:
    - Python 3.x
    - .NET Framework (pre-installed on most Windows systems)

2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1.  **Configure Games**:
    Edit `config.json` to add the games you want to trigger HDR.
    ```json
    {
      "games": [
        {
          "name": "Cyberpunk 2077",
          "folder": "Cyberpunk 2077",
          "exe": "Cyberpunk2077.exe"
        }
      ]
    }
    ```
    - `name`: Friendly name for logs.
    - `folder`: Part of the folder path to match (prevents false positives).
    - `exe`: The executable name.

2.  **Run the Application**:
    ```bash
    python main.py
    ```
    To run without a console window:
    ```bash
    pythonw main.py
    ```

3.  **System Tray**:
    - Right-click the "HDR" icon in the system tray.
    - Select **Start with Windows** to enable auto-start.
    - Select **Exit** to close the application.

## How it Works
- The application compiles a small C# helper (`hdr_controller.exe`) on first run.
- This helper simulates the `Win + Alt + B` keyboard shortcut to toggle HDR.
- The Python script monitors process creation and termination to trigger the helper.
