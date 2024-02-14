import can
import threading
import PySimpleGUI as sg
from uploadfirmware import UploadFirmware

from sys import platform
if platform == "linux" or platform == "linux2":
    # linux
    import subprocess
    def get_can_interfaces():
        cans_raw = subprocess.run([
            '/bin/bash', '-c', 
            "echo $(ip link show | grep -o -P ': can.{0,1}' | tr -d ': ')"], 
            stdout=subprocess.PIPE, 
            stderr=subprocess.PIPE)
        cans_raw = cans_raw.stdout.decode('utf-8').replace('\n','').split(" ")
        return cans_raw
elif platform == "win32" or platform == "cygwin":
    # Windows, not implemented yet
    def get_can_interfaces():
        return []

layout = [
    [sg.Text('Select CAN interface: '), sg.DropDown(get_can_interfaces(), enable_events=True,  readonly=True, key='-CANINTERFACE-', default_value="None"),
     sg.Text('Select uC: '), sg.DropDown(["TOP", "BOTTOM", "SENSE"], enable_events=True,  readonly=True, key='-UCOBJETIVE-', default_value="TOP")],
    [sg.Text('Bootloader waiting ms: '), sg.Input(key='-TIMEOUT-',size =(10, 1), enable_events=True, default_text="10000")],
    [sg.Text('Bootloader attempts: '), sg.Input(key='-ATTEMPTS-',size =(10, 1), enable_events=True, default_text="10"), sg.Checkbox("Unmute CAN bus after upload", key='-UNMUTE-')],
    [sg.Text('Firmware path: '), sg.InputText(size=(30, 1), disabled=True, enable_events=True, key="-FILE-"),sg.FileBrowse()],
    [sg.Button('Upload!'),sg.ProgressBar(100, orientation='h', expand_x=True, size=(20, 20),  key='-PBAR-')]
]
# sg.theme('SystemDefault')
window = sg.Window("CAN firmware upload", layout)
while True:
    event, values = window.read()
    # print(event, values)
    if event is None or event == "Cancel":
        break
    elif event == "Upload!":
        values_tmp = values.copy()
        values_tmp.pop('-UNMUTE-')
        if not all(values_tmp.values()):
            sg.popup("Missing fields")
            continue
        window['Upload!'].update(disabled=True)
        with can.Bus(interface='socketcan', channel=values['-CANINTERFACE-'], bitrate=1000000) as bus:
            uc_upload = UploadFirmware(bus, values['-UCOBJETIVE-'], values['-FILE-'],int(values['-TIMEOUT-']))
            print("Mute CAN bus")
            uc_upload.mute_canbus()
            if uc_upload.enter_bootmode(int(values['-ATTEMPTS-'])):
                print("Boot mode on")
                threading.Thread(target=lambda uc: uc.upload(), args=([uc_upload]), daemon=True).start()
                while uc_upload.upload_status()<99.0:
                    window['-PBAR-'].update(current_count=uc_upload.upload_status())
                sg.popup("Upload complete!")
            else:
                sg.popup("Fail to upload firmware!")
            if str(values['-UNMUTE-']).upper() == "TRUE":
                print("Unmute CAN bus")
                uc_upload.unmute_canbus()
        window['-PBAR-'].update(current_count=0)
        window['Upload!'].update(disabled=False)
    elif event == "-FILE-":
        print(values["-FILE-"])
        pass
    elif event == '-TIMEOUT-' and values['-TIMEOUT-']:
        try:
            in_as_int = int(values['-TIMEOUT-'])
        except:
            if not (len(values['-TIMEOUT-']) == 1 and values['-TIMEOUT-'][0] == '-'):
                window['-TIMEOUT-'].update(values['-TIMEOUT-'][:-1])
    elif event == '-ATTEMPTS-' and values['-ATTEMPTS-']:
        try:
            in_as_int = int(values['-ATTEMPTS-'])
        except:
            if not (len(values['-ATTEMPTS-']) == 1 and values['-ATTEMPTS-'][0] == '-'):
                window['-ATTEMPTS-'].update(values['-ATTEMPTS-'][:-1])
    elif event == sg.WIN_CLOSED or event == 'Exit':
      break
window.close()
