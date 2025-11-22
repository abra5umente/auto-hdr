import wmi
import time
import json
import os
import subprocess
import sys
import logging
import threading
import pystray
from PIL import Image, ImageDraw
import winshell
from win32com.client import Dispatch

# Configuration
CONFIG_FILE = 'config.json'
HDR_CONTROLLER_SRC = 'hdr_controller.cs'
HDR_CONTROLLER_EXE = 'hdr_controller.exe'
APP_NAME = "Auto-HDR"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_config():
    if not os.path.exists(CONFIG_FILE):
        logging.error(f"Config file {CONFIG_FILE} not found.")
        return None
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        logging.error(f"Error loading config: {e}")
        return None

def compile_hdr_controller():
    if not os.path.exists(HDR_CONTROLLER_SRC):
        logging.error(f"Source file {HDR_CONTROLLER_SRC} not found.")
        return False
    
    try:
        subprocess.run(['csc', '/?'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        dotnet_root = os.path.join(os.environ['WINDIR'], 'Microsoft.NET', 'Framework64')
        if os.path.exists(dotnet_root):
            versions = sorted([d for d in os.listdir(dotnet_root) if d.startswith('v4.')], reverse=True)
            if versions:
                csc_path = os.path.join(dotnet_root, versions[0], 'csc.exe')
                if os.path.exists(csc_path):
                    logging.info(f"Found csc at {csc_path}")
                    cmd = [csc_path, '/out:' + HDR_CONTROLLER_EXE, HDR_CONTROLLER_SRC]
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode == 0:
                        logging.info("Successfully compiled hdr_controller.exe")
                        return True
                    else:
                        logging.error(f"Compilation failed: {result.stderr}")
                        return False
        
        logging.error("csc compiler not found. Please ensure .NET Framework is installed.")
        return False

    cmd = ['csc', '/out:' + HDR_CONTROLLER_EXE, HDR_CONTROLLER_SRC]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        logging.info("Successfully compiled hdr_controller.exe")
        return True
    else:
        logging.error(f"Compilation failed: {result.stderr}")
        return False

def toggle_hdr(action):
    if not os.path.exists(HDR_CONTROLLER_EXE):
        logging.error("HDR controller executable not found.")
        return

    logging.info(f"Toggling HDR: {action}")
    # Use CREATE_NO_WINDOW to hide the console window of the subprocess
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    subprocess.run([HDR_CONTROLLER_EXE, action], startupinfo=startupinfo)

def create_image():
    # Load the icon from file if it exists, otherwise generate fallback
    icon_path = 'icon.png'
    if os.path.exists(icon_path):
        return Image.open(icon_path)
    
    # Generate an image for the system tray icon
    width = 64
    height = 64
    color1 = "black"
    color2 = "white"
    image = Image.new('RGB', (width, height), color1)
    dc = ImageDraw.Draw(image)
    dc.rectangle((width // 2, 0, width, height // 2), fill=color2)
    dc.rectangle((0, height // 2, width // 2, height), fill=color2)
    return image

def get_startup_path():
    return os.path.join(winshell.startup(), f"{APP_NAME}.lnk")

def is_startup_enabled(item):
    return os.path.exists(get_startup_path())

def toggle_startup(icon, item):
    link_path = get_startup_path()
    if os.path.exists(link_path):
        try:
            os.remove(link_path)
            logging.info("Removed from startup")
        except Exception as e:
            logging.error(f"Failed to remove startup shortcut: {e}")
    else:
        try:
            target = sys.executable
            # If running as script, target pythonw and pass script path
            # If frozen (exe), target executable
            w_dir = os.getcwd()
            args = ""
            
            if getattr(sys, 'frozen', False):
                target = sys.executable
            else:
                # Use pythonw.exe to run without console
                target = os.path.join(os.path.dirname(sys.executable), 'pythonw.exe')
                script_path = os.path.abspath(__file__)
                args = f'"{script_path}"'

            shell = Dispatch('WScript.Shell')
            shortcut = shell.CreateShortCut(link_path)
            shortcut.Targetpath = target
            shortcut.Arguments = args
            shortcut.WorkingDirectory = w_dir
            shortcut.IconLocation = target
            shortcut.save()
            logging.info("Added to startup")
        except Exception as e:
            logging.error(f"Failed to create startup shortcut: {e}")

def on_quit(icon, item):
    global stop_event
    stop_event.set()
    icon.stop()

import pythoncom

def monitor_loop(stop_event):
    pythoncom.CoInitialize()
    config = load_config()
    if not config:
        return

    if not os.path.exists(HDR_CONTROLLER_EXE):
        logging.info("Compiling HDR controller...")
        if not compile_hdr_controller():
            return

    c = wmi.WMI()
    active_hdr_game_pids = set()

    logging.info("Monitoring started...")

    while not stop_event.is_set():
        try:
            current_processes = {}
            try:
                procs = c.Win32_Process(['ProcessId', 'Name', 'ExecutablePath'])
                for p in procs:
                    if p.ProcessId and p.Name:
                        current_processes[p.ProcessId] = {
                            'name': p.Name,
                            'path': p.ExecutablePath
                        }
            except Exception as e:
                logging.error(f"Error listing processes: {e}")
                time.sleep(1)
                continue

            matched_pids = set()
            
            for pid, p_info in current_processes.items():
                p_name = p_info['name']
                p_path = p_info['path']
                
                if not p_path: continue

                for game in config['games']:
                    if game['exe'].lower() == p_name.lower():
                        if game['folder'].lower() in p_path.lower():
                            matched_pids.add(pid)
                            
                            if pid not in active_hdr_game_pids:
                                logging.info(f"Game detected: {game['name']} (PID: {pid})")
                                if not active_hdr_game_pids:
                                    toggle_hdr('on')
                                active_hdr_game_pids.add(pid)

            exited_pids = []
            for pid in list(active_hdr_game_pids):
                if pid not in matched_pids:
                    if pid not in current_processes:
                        logging.info(f"Game exited: PID {pid}")
                        exited_pids.append(pid)
            
            for pid in exited_pids:
                active_hdr_game_pids.remove(pid)
            
            if exited_pids and not active_hdr_game_pids:
                 toggle_hdr('off')

            time.sleep(2)

        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            time.sleep(1)

stop_event = threading.Event()

def main():
    # Start monitor thread
    t = threading.Thread(target=monitor_loop, args=(stop_event,))
    t.daemon = True
    t.start()

    # Create tray icon
    menu = pystray.Menu(
        pystray.MenuItem("Start with Windows", toggle_startup, checked=is_startup_enabled),
        pystray.MenuItem("Exit", on_quit)
    )

    icon = pystray.Icon("Auto-HDR", create_image(), "Auto-HDR", menu)
    icon.run()

    # Wait for thread to finish (if icon.run returns)
    stop_event.set()
    t.join()

if __name__ == "__main__":
    main()
