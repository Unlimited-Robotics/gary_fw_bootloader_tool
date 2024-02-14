# Gary Bootloader Tool

## Install dependencies

```bash
python3 -m pip install -r requirements.txt
```

## Usage

### Mandatory

- CAN Interface: `can0`,`can1`, ...
- uC Objetive: TOP, BOTTOM or SENSE
- Firmware path: hex file with the firmware to upload(ihex format).

### Optional

- Timeout: timeout in ms to wait for bootloader msg, default 10000.
- Attempts: attempts until giving up trying to start the bootloader, default 1.
- Unmute: unmute CAN bus after upload firmware, default false.

From terminal:

```bash
python3 uploadfirmware.py <can_interface> <uc_objetive> <firmware_path>
```

 you can run the gui version and set parameters manually.

 ```bash
python3 uploadfirmware-gui.py
```