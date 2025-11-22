import wmi
import time
import json
import os
import subprocess
import sys
import logging

# Configuration
CONFIG_FILE = 'config.json'
HDR_CONTROLLER_SRC = 'hdr_controller.cs'
HDR_CONTROLLER_EXE = 'hdr_controller.exe'

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
    
    # Check if csc is in path
    try:
        subprocess.run(['csc', '/?'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError:
        # Try to find csc in standard .NET locations
        dotnet_root = os.path.join(os.environ['WINDIR'], 'Microsoft.NET', 'Framework64')
        if os.path.exists(dotnet_root):
            # Find the latest version
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

    # csc is in path
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
    subprocess.run([HDR_CONTROLLER_EXE, action])

def main():
    config = load_config()
    if not config:
        return

    if not os.path.exists(HDR_CONTROLLER_EXE):
        logging.info("Compiling HDR controller...")
        if not compile_hdr_controller():
            return

    c = wmi.WMI()
    # watcher_start = c.Win32_ProcessStartTrace.watch()
    # watcher_stop = c.Win32_ProcessStopTrace.watch()

    # Track running games to avoid double toggling
    # Key: pid, Value: game_name
    running_games = {} 

    logging.info("Monitoring started...")

    # We need to poll or use threads because we have two watchers. 
    # Or we can just use a loop with timeout.
    # WMI watchers are blocking by default.
    # Let's use a simpler polling approach for now to keep it single threaded and robust,
    # or just use one watcher for everything? No, they are different events.
    # Actually, raw_wql query might be better for polling, but watch() is event driven.
    # Let's use a loop that checks existing processes periodically + event listener?
    # No, let's just use a simple polling loop for "Process exists" which is easier than maintaining state with events if we miss one.
    # BUT the user asked for "monitors user-specified folders for application launches".
    # Polling is safer.
    
    # Re-reading requirements: "when application launches... flip HDR ON... when that application exits... flip HDR off"
    
    active_hdr_game_pids = set()

    while True:
        try:
            # Reload config dynamically? Maybe not for now.
            
            # Get all running processes
            current_processes = {} # pid -> name/path
            try:
                procs = c.Win32_Process(['ProcessId', 'Name', 'ExecutablePath'])
                # logging.info(f"Found {len(procs)} processes")
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

            # Check for new matches
            matched_pids = set()
            
            for pid, p_info in current_processes.items():
                p_name = p_info['name']
                p_path = p_info['path']
                
                if not p_path: continue # System processes might not have path accessible

                # logging.info(f"Checking {p_name} at {p_path}")

                for game in config['games']:
                    # Check if exe matches
                    if game['exe'].lower() == p_name.lower():
                        # Check if folder matches
                        # Normalize paths
                        if game['folder'].lower() in p_path.lower():
                            matched_pids.add(pid)
                            
                            # If this is a NEW match (not in our active set)
                            if pid not in active_hdr_game_pids:
                                logging.info(f"Game detected: {game['name']} (PID: {pid})")
                                # If this is the FIRST game, toggle HDR ON
                                if not active_hdr_game_pids:
                                    toggle_hdr('on')
                                active_hdr_game_pids.add(pid)

            # Check for exits
            # Identify PIDs that were active but are no longer running
            exited_pids = []
            for pid in list(active_hdr_game_pids):
                if pid not in matched_pids:
                    # Double check if it's really gone (sometimes WMI is slow?)
                    # If it's not in current_processes, it's gone.
                    if pid not in current_processes:
                        logging.info(f"Game exited: PID {pid}")
                        exited_pids.append(pid)
            
            for pid in exited_pids:
                active_hdr_game_pids.remove(pid)
            
            # If no games are running anymore, toggle HDR OFF
            if exited_pids and not active_hdr_game_pids:
                 toggle_hdr('off')

            time.sleep(2) # Poll every 2 seconds

        except KeyboardInterrupt:
            logging.info("Exiting...")
            break
        except Exception as e:
            logging.error(f"Unexpected error: {e}")
            time.sleep(1)

if __name__ == "__main__":
    main()
