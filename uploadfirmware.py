# Import libraries
# Install requirements with: python3 -m pip install -r requirements.txt
import sys
import can
import time
import argparse
from intelhex import IntelHex
from alive_progress import alive_bar

class UploadFirmware():
    CAN_FREE_WAITING_SECONDS = 10
    SENSE_ID = 0X102
    TOP_ID = 0X103
    BOT_ID = 0X104
    BOOTLOADER_ID = 0x9A
    BOOTLOADER_MSG = [0x21, 0x53, 0x57, 0x55, 0x00, 0x00, 0x00, 0x00]
    RESPONSE_ID = 0x099
    MSG_FF = [0x00, 0x00, 0xFF, 0x00, 0x00, 0x00]
    MSG_01 = [0x00, 0x00, 0x01, 0x00, 0x00, 0x00]
    MSG_00 = [0]*6
    MSG_5353 = [0x53, 0x53]
    MSG_5045 = [0x50, 0x45]
    MSG_FF00 = [0xFF, 0x00]
    UC_ID_LIST = [TOP_ID,BOT_ID,SENSE_ID]

    def __init__(self,
                    can_bus: can.Bus,
                    uc: str,
                    firmware_path: str,
                    boot_timeout_ms: int = 30000):
        uc = uc.upper()
        if uc == "TOP":
            self.uc_id = 0
        elif uc == "BOTTOM" or uc == "BOT":
            self.uc_id = 1
        elif uc == "SENSE":
            self.uc_id = 2
        else:
            raise Exception("Unspecified microcontroller")
        if boot_timeout_ms<1000:
            raise Exception("Boot timeout must be greater than 1000")
        self.can_bus = can_bus
        self.enter_boot_failed = 0
        self.last_delta = time.time()
        ih = IntelHex()
        ih.loadhex(firmware_path)
        self.firmware_ihex = ih.tobinarray().tolist()
        self.boot_timeout_ns = boot_timeout_ms*10**6
        self.bootloading_mode = False
        self.upload_status_percentage = 0.0
    
    
    def can_send(self, data, id):
        """:param id: Spam the bus with messages including the data id."""
        msg = can.Message(arbitration_id=id, data=data, is_extended_id=False)
        try:
            self.can_bus.send(msg)
        except can.CanError:
            print("CAN message NOT sent")
        time.sleep(100e-6)
    
    def mute_canbus(self):
        self.can_send(self.MSG_5353 + self.MSG_FF, self.TOP_ID)
        self.can_send(self.MSG_5353 + self.MSG_FF, self.TOP_ID)
        self.can_send(self.MSG_5045 + self.MSG_00, self.TOP_ID)
        self.can_send(self.MSG_5045 + self.MSG_00, self.TOP_ID)
        self.can_send(self.MSG_5353 + self.MSG_FF, self.SENSE_ID)
        self.can_send(self.MSG_5353 + self.MSG_FF, self.SENSE_ID)
        self.can_send(self.MSG_5045 + self.MSG_00, self.SENSE_ID)
        self.can_send(self.MSG_5045 + self.MSG_00, self.SENSE_ID)
        self.can_send(self.MSG_5353 + self.MSG_FF, self.BOT_ID)
        self.can_send(self.MSG_5353 + self.MSG_FF, self.BOT_ID)
        self.can_send(self.MSG_5045 + self.MSG_00, self.BOT_ID)
        self.can_send(self.MSG_5045 + self.MSG_00, self.BOT_ID)
        self.can_send(self.MSG_5353 + self.MSG_00, self.BOT_ID)
        self.can_send(self.MSG_FF00 + self.MSG_00, self.BOOTLOADER_ID)
        self.can_send(self.MSG_FF00 + self.MSG_00, self.BOOTLOADER_ID)
        time.sleep(1.0)


    def unmute_canbus(self):
        self.can_send(self.MSG_5045 + self.MSG_01, self.TOP_ID)
        self.can_send(self.MSG_5045 + self.MSG_01, self.TOP_ID)
        self.can_send(self.MSG_5353 + self.MSG_FF, self.SENSE_ID)
        self.can_send(self.MSG_5353 + self.MSG_FF, self.SENSE_ID)
        self.can_send(self.MSG_5045 + self.MSG_00, self.SENSE_ID)
        self.can_send(self.MSG_5045 + self.MSG_00, self.SENSE_ID)
        self.can_send(self.MSG_5353 + self.MSG_FF, self.BOT_ID)
        self.can_send(self.MSG_5353 + self.MSG_FF, self.BOT_ID)
        self.can_send(self.MSG_5045 + self.MSG_00, self.BOT_ID)
        self.can_send(self.MSG_5045 + self.MSG_00, self.BOT_ID)
        self.can_send(self.MSG_FF00 + self.MSG_00, self.BOOTLOADER_ID)
        self.can_send(self.MSG_FF00 + self.MSG_00, self.BOOTLOADER_ID)

    def get_time_delta(self, last_time = 0):
        if last_time == 0:
            return 0
        else:
            return time.time()-last_time
        
    def upload(self):
        if not self.bootloading_mode:
            print("First put the uC on bootloading mode")
            return
        print(f"Checking if CAN is free for {self.CAN_FREE_WAITING_SECONDS}s")
        bus_busy = False
        t0 = time.time()
        while time.time() < (t0+self.CAN_FREE_WAITING_SECONDS):
            tmp = self.can_bus.recv(0.1)
            if tmp is None:
                continue
            if tmp.arbitration_id!=self.RESPONSE_ID:
                bus_busy = True
                break
        if bus_busy:
            print("CAN bus busy")
            return
        print("CAN bus free")
        counter = 0
        pkg_lost = 0
        with alive_bar(int(len(self.firmware_ihex)/4)) as bar:
            for i in range(0,len(self.firmware_ihex),4):
                msg = [(counter>>24)&0xFF, (counter>>16)&0xFF, 
                       (counter>>8)&0xFF, counter&0xFF] + \
                    self.firmware_ihex[i:i+4]
                counter+=1
                attempts = 0
                while True:
                    if (attempts%100 == 0):
                        self.can_send(msg,self.BOOTLOADER_ID)
                    attempts+=1
                    ack = self.can_bus.recv(0.01) # wait ACK
                    if ack!= None and ack.arbitration_id == self.RESPONSE_ID:
                        if ack.data != bytearray(msg):
                            pkg_lost+=1
                            print("Packet lost, send again\n")
                            continue
                        else:
                            break
                bar()
                self.upload_status_percentage = i*100
                self.upload_status_percentage /= len(self.firmware_ihex)-1
        time.sleep(0.2)
        self.can_send([0x01]+[0xFF]*7, self.BOOTLOADER_ID)
        time.sleep(0.2)
        self.bootloading_mode = False
        self.upload_status_percentage = 0.0
        print("Data send!")
        print(f"Packages lost: {pkg_lost}")

    def enter_bootmode(self, attempts:int = 10):
        attempt = 0
        while attempt<attempts:
            attempt+=1
            print(f"Entering uC in bootloading mode (attempt {attempt})")
            self.can_send(self.BOOTLOADER_MSG,self.UC_ID_LIST[self.uc_id])
            start_time = time.time_ns()
            while True:
                ack = self.can_bus.recv(0.5)
                if (time.time_ns() - start_time) > self.boot_timeout_ns:
                    print(f"TIMEOUT (attempts: {attempts}, attemp: {attempt})")
                    start_time = time.time_ns()
                    break
                if ack==None:
                    continue
                elif ack.arbitration_id == self.RESPONSE_ID:
                    if  (self.uc_id==0 and ack.data[-1] == 3) or \
                        (self.uc_id==1 and ack.data[-1] == 4) or \
                        (self.uc_id==2 and ack.data[-1] == 2):
                        print("uC on bootloading mode!")
                        self.bootloading_mode = True
                        return True
                else:
                    continue
        print("Enter on bootloading mode failed")
        return False
    
    def upload_status(self):
        return self.upload_status_percentage

def main() -> int:
    parser = argparse.ArgumentParser(description="Just an example",
                                 formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("-t", "--timeout-ms", type=int, default=10000, help="Bootloader timeout, must be greater than 1000")
    parser.add_argument("-a", "--attempts", type=int, default=1, help="Bootloader atempts")
    parser.add_argument("-u", "--unmute", default="False", help="Unmute CAN bus after upload firmware, default to False")
    parser.add_argument("can_interface", type=str, help="CAN interface used to communicate with the microcontroller (can0, can1, etc)")
    parser.add_argument("uc_objetive", type=str, help="TOP, BOTTOM or SENSE")
    parser.add_argument("firmware_path", type=str, help="Firmware path to upload to the microcontroller")
    args = parser.parse_args()
    config = vars(args)
    # print(config)
    with can.Bus(interface='socketcan', channel=config['can_interface'], bitrate=1000000) as bus:
        uc_upload = UploadFirmware(bus, config['uc_objetive'], config['firmware_path'],config['timeout_ms'])
        print("Muting CAN bus")
        uc_upload.mute_canbus()
        if uc_upload.enter_bootmode(config['attempts']):
            print("Boot mode on")
            uc_upload.upload()
        else:
            print("Fail to upload firmware")
        if config['unmute'].upper() == "TRUE":
            print("Unmuting CAN bus")
            uc_upload.unmute_canbus()
    return 0

if __name__ == '__main__':
    sys.exit(main())