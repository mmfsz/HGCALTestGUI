#!/usr/bin/python

import struct, fcntl, os, sys

def determineDefaults():
    # see if this is a Raspberry Pi, in which case the defaults are clear
    with open("/proc/cpuinfo") as f:
        for lines in f:
            if lines.find("Model")>=0 and lines.find("Raspberry")>=0:
                return {'protocol':'I2C','device':'/dev/i2c-1'}
    # look for a connections file in the project-standard location
    if os.path.exists("/opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml"):
        return {'protocol':'IC', 'connections': "file:///opt/cms-hgcal-firmware/hgc-test-systems/active/uHAL_xml/connections.xml", 'device':'TOP'}
    return {'protocol':'IC', 'connections': "file://connections.xml", 'device':'zcu' }

class I2CException(Exception):
    """Raised when an I2C error was encountered"""
    pass

class iic:

    def __init__(self, mode="I2C"):
        self.fd = None
        self.hw = None
        self.mode = "I2C"
        if mode in ("I2C","IC"):
            self.mode = mode
        else:
            print("mode not supported, will use I2C mode (options: I2C, IC)")
        if mode=="IC":
            global uhal
            import uhal

    def connect(self,dev="/dev/i2c-23",addr=0x70,xml="file://connections.xml",uhaldevice="zcu"):
        if self.mode == "I2C":
            self.fd = os.open(dev, os.O_RDWR)
            fcntl.ioctl(self.fd,0x0703,addr)
        elif self.mode == "IC":
            uhal.setLogLevelTo( uhal.LogLevel.WARNING )
            self.hw = uhal.ConnectionManager(xml).getDevice(uhaldevice)
            frontend=self.hw.getNode("frontend")
            # disable I2C
            frontend.getNode("CTL.I2C_ENABLE").write(0)
            self.hw.dispatch()

    def close(self):
        if self.fd:
            os.close(self.fd)
            self.fd=None
        elif self.hw:
            # enable I2C again so there are no surprises
            frontend=self.hw.getNode("frontend")
            frontend.getNode("CTL.I2C_ENABLE").write(1)
            self.hw.dispatch()
            self.hw=None

    def write_lpgbt(self,reg,val, lpgbt='A'):
        if lpgbt!='A':
            self.write_lpgbt_trig(lpgbt,reg,val)
        elif self.mode == "I2C":
            self.write([reg&0xFF,((reg>>8)&0xFF),val])
        elif self.mode == "IC":
            self.write_IC(reg,val)

    def read_lpgbt(self,reg, lpgbt='A'):
        if lpgbt!='A':
            return self.read_lpgbt_trig(lpgbt,reg)
        elif self.mode == "I2C":
            self.write([reg&0xFF,((reg>>8)&0xFF)])
            return self.read(1)[0]
        elif self.mode == "IC":
            return self.read_IC(reg)[0]

    def read(self,nbytes):
        # For use with I2C path
        rv=os.read(self.fd,nbytes)
        if rv is not None:
            rvi=[]
            for item in rv:
               if sys.version_info > (3, 0):
                  rvi.append(item)
               else:
                  rvi.append(ord(item))
            return rvi
        else: return None

    def write(self,mybuf):
        # For use with I2C path
        #s=""
        #for val in (mybuf):
        #    s += chr(val)
        #os.write(self.fd,s)
        os.write(self.fd,bytes(bytearray(mybuf)))

    def write_lpgbt_trig(self,lpgbt_id,reg,val):
        # Assuming a one-byte val
        lpgbt_addr = None
        if lpgbt_id in ["B",1]:
            lpgbt_addr = 0x71
        elif lpgbt_id in ["C",2]:
            lpgbt_addr = 0x72
        elif lpgbt_id in ["D",3]:
            lpgbt_addr = 0x73
        else:
            print("Please provide existing slave lpgbt id. Options are B,C,D or 1,2,3")
            return

        # set speed to 100 kHz, and write three bytes
        self.write_lpgbt(0x0f9, ((3) << 2)+0x0)
        # send command to write to control register
        self.write_lpgbt(0x0fd, 0x0)

        # Set up what all should be sent, and where                                                                     
        self.write_lpgbt(0x0f8, lpgbt_addr)
        self.write_lpgbt(0x0f9, reg&0xFF)
        self.write_lpgbt(0x0fa, (reg>>8)&0xFF)
        self.write_lpgbt(0x0fb, val)
        self.write_lpgbt(0x0fd, 0x8)

        # initiate actual write
        self.write_lpgbt(0x0fd, 0xc)

        # Check the status of the transaction
        status = self.read_lpgbt(0x176)
        while not (status & 0x4):
            if status & 0x40:
                print("Problem: I2C NACK")
                raise I2CException("I2C NACK encountered")
            elif status & 0x8:
                print("Problem: SDA low before starting transaction")
                raise I2CException("SDA low before starting transaction")
            else:
                status = self.read_lpgbt(0x176)


    def read_lpgbt_trig(self,lpgbt_id,reg):
        # Reading back one byte from reg
        lpgbt_addr = None
        if lpgbt_id in ["B",1]:
            lpgbt_addr = 0x71
        elif lpgbt_id in ["C",2]:
            lpgbt_addr = 0x72
        elif lpgbt_id in ["D",3]:
            lpgbt_addr = 0x73
        else:
            print("Please provide existing slave lpgbt id. Options are B,C,D or 1,2,3")
            return

        # set speed to 100 kHz, and write 2 bytes (for the reg address)
        self.write_lpgbt(0x0f9, ((2)<<2)+0x0 )
        # send command to write to control register
        self.write_lpgbt(0x0fd, 0x0)

        self.write_lpgbt(0x0f8, lpgbt_addr)
        self.write_lpgbt(0x0f9, reg&0xFF)
        self.write_lpgbt(0x0fa, (reg>>8)&0xFF)
        self.write_lpgbt(0x0fd, 0x8)

        # initiate actual write
        self.write_lpgbt(0x0fd, 0xc)

        # Check the status of the transaction
        status = self.read_lpgbt(0x176)
        while not (status & 0x4):
            if status & 0x40:
                print("Problem: I2C NACK")
                raise I2CException("I2C NACK encountered")
            elif status & 0x8:
                print("Problem: SDA low before starting transaction")
                raise I2CException("SDA low before starting transaction")
            else:
                status = self.read_lpgbt(0x176)

        # Now try reading
        # Write command word for reading
        self.write_lpgbt(0x0f8, lpgbt_addr)
        self.write_lpgbt(0x0fd, 0x3)

        status = self.read_lpgbt(0x176)
        while not (status & 0x4):
            if status & 0x40:
                print("Problem: I2C NACK")
                raise I2CException("I2C NACK encountered")
            elif status & 0x8:
                print("Problem: SDA low before starting transaction")
                raise I2CException("SDA low before starting transaction")
            else:
                status = self.read_lpgbt(0x176)

        # Read back
        output = self.read_lpgbt(0x178)

        return output


    def write_vtrx(self,reg,val):
        # Reading back one byte from reg
        vtrx_addr = 0x50

        # set speed to 100 kHz, and write 2 bytes
        self.write_lpgbt(0x100, ((2)<<2)+0x0 )
        # send command to write to control register
        self.write_lpgbt(0x104, 0x0)

        self.write_lpgbt(0x0ff, vtrx_addr)
        self.write_lpgbt(0x100, reg&0xFF)
        self.write_lpgbt(0x102, val)
        self.write_lpgbt(0x104, 0x8)

        # initiate actual write
        self.write_lpgbt(0x104, 0xc)

        # Check the status of the transaction
        status = self.read_lpgbt(0x18b)
        while not (status & 0x4):
            if status & 0x40:
                print("Problem: I2C NACK")
                raise I2CException("I2C NACK encountered")
            elif status & 0x8:
                print("Problem: SDA low before starting transaction")
                raise I2CException("SDA low before starting transaction")
            else:
                status = self.read_lpgbt(0x18b)

    def read_vtrx(self,reg):
        # Reading back one byte from reg
        vtrx_addr = 0x50

        # set speed to 100 kHz, and write 1 bytes (for the reg address)
        self.write_lpgbt(0x100, ((1)<<2)+0x0 )
        # send command to write to control register
        self.write_lpgbt(0x104, 0x0)

        self.write_lpgbt(0x0ff, vtrx_addr)
        self.write_lpgbt(0x100, reg&0xFF)  #vtrx has 1-byte address
        self.write_lpgbt(0x104, 0x8)

        # initiate actual write
        self.write_lpgbt(0x104, 0xc)

        # Check the status of the transaction
        status = self.read_lpgbt(0x18b)
        while not (status & 0x4):
            if status & 0x40:
                print("Problem: I2C NACK")
                raise I2CException("I2C NACK encountered")
            elif status & 0x8:
                print("Problem: SDA low before starting transaction")
                raise I2CException("SDA low before starting transaction")
            else:
                status = self.read_lpgbt(0x18b)

        # Now try reading
        # Write command word for reading
        self.write_lpgbt(0x0ff, vtrx_addr)
        self.write_lpgbt(0x104, 0x3)

        status = self.read_lpgbt(0x18b)
        while not (status & 0x4):
            if status & 0x40:
                print("Problem: I2C NACK")
                raise I2CException("I2C NACK encountered")
            elif status & 0x8:
                print("Problem: SDA low before starting transaction")
                raise I2CException("SDA low before starting transaction")
            else:
                status = self.read_lpgbt(0x18b)

        # Read back
        output = self.read_lpgbt(0x18d)

        return output




    ## ----------- Start IC stuff ----------- ##
    def write_IC(self, reg, val):
        backend = self.hw.getNode("backend")
        backend.getNode("IC_TX_I2C_ADDR").write(0x70)
        self.hw.dispatch()
        backend.getNode("IC_TX_REG_ADDR").write(reg)
        backend.getNode("IC_TX_DATA").write(val)
        backend.getNode("CTL.IC_TX_FIFO_LOAD").write(1)
        self.hw.dispatch()
        backend.getNode("CTL.IC_START_WRITE").write(1)  # write 1, gets cleared automatically
        self.hw.dispatch()


    def read_IC(self, reg, nread=1):
        backend=self.hw.getNode("backend")
        backend.getNode("IC_TX_I2C_ADDR").write(0x70)
        self.hw.dispatch()
        backend.getNode("IC_TX_REG_ADDR").write(reg)
        backend.getNode("IC_TX_N_READ").write(nread)
        self.hw.dispatch()
        backend.getNode("CTL.IC_START_READ").write(1)
        self.hw.dispatch()
        empty= backend.getNode("IC_RX_EMPTY").read()
        self.hw.dispatch()

        words = []
        while not empty:
            word = backend.getNode("IC_RX_DATA").read()
            self.hw.dispatch()
            words.append(word)
            backend.getNode("CTL.IC_RX_FIFO_ADV").write(1)
            self.hw.dispatch()
            empty= backend.getNode("IC_RX_EMPTY").read()
            self.hw.dispatch()

        return words[7:-1]
