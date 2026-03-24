#!/usr/bin/python

import iic
import time
import argparse

class mm_power_man:

   GPIO_ENABLE_REG=2
   GPIO_STATUS_REG=1
   GPIO_ENABLE_REG_CFG=6
   GPIO_STATUS_REG_CFG=7

   def __init__(self,device,board):
      addrs = {
	1:[0x27,0x46],
	2:[0x26,0x74],
	3:[0x25,0x64],
	4:[0x24,0x56]
	}
      self.adc=iic.iic()
      self.adc.connect(dev=device,addr=addrs[board][1])
      self.gpio=iic.iic()
      self.gpio.connect(dev=device,addr=addrs[board][0])
      if self.gpio_read(self.GPIO_ENABLE_REG_CFG)!=0xF0:
         self.gpio_write(self.GPIO_ENABLE_REG,0)
         self.gpio_write(self.GPIO_ENABLE_REG_CFG,0xF0)

   def adc_read(self,chan,diff=True):
      cmd=0x80|0x20|chan
      if not diff: cmd=cmd|0x10
      time.sleep(0.16)
      self.adc.write([cmd])
      time.sleep(0.16)
      x=self.adc.read(3)
      val=((int(x[0])&0x3F)<<10)|(int(x[1])<<2)|(int(x[2])>>6)
      if (int(x[0])&0xC0)==0x40:
         val=val-0x10000
      if (int(x[0])&0xC0)==0xC0:
         val=100000
      if (int(x[0])&0xC0)==0x00:
         val=-100000
      # calibrate
      val=val*1.25000/0x10000
      return val

   def input_voltage(self):
      return self.adc_read(0,False)+1.25
      #return self.adc_read(0,False)

   def current(self,module,analog=False):
      chan=(module-1)*2
      resistor = 0.01
      if analog:
          chan = chan+1
          return -0.848*self.adc_read(chan,True)/100/resistor
      #0.848 is a magic number found by calibrating across the expected useful range.
      return 0.848*self.adc_read(chan,True)/resistor

   def voltage_temp(self,module,analog=False):
      chan=(module-1)*2+1
      if analog:
          chan = chan+1
      return -self.adc_read(chan,False)

   def gpio_write(self,ireg,value):
      self.gpio.write([int(ireg),int(value)])

   def gpio_read(self,ireg):
      self.gpio.write([ireg])
      x=self.gpio.read(1)
      return x[0]

   def set_enabled(self,imodule=0,enabled=True):
      x=self.gpio_read(self.GPIO_ENABLE_REG)
      if imodule==0:
         if enabled:
            x=x|0xF
         else:
            x=x&0xF0
      else:
         x=x|(1<<(imodule-1))
         if not enabled:
            x=x^(1<<(imodule-1))
      self.gpio_write(self.GPIO_ENABLE_REG,x)

   def status_flags(self):
      en=self.gpio_read(self.GPIO_ENABLE_REG)
      stat=self.gpio_read(self.GPIO_STATUS_REG)
      flags={}
      for i in range(0,4):
         flags["M%d.ENABLED"%(i+1)]=((en&(1<<i))!=0)
         flags["M%d.1V8_OK"%(4-i)]=((stat&(1<<(i*2)))!=0)
         flags["M%d.9V_OK"%(4-i)]=((stat&(1<<(i*2+1)))!=0)
      return flags


if __name__ == "__main__":

   parser=argparse.ArgumentParser(description="Simplistic MM power tray interface")
   parser.add_argument('--status',action='store_true',help='Full dump of all registers')
   parser.add_argument('--device',type=str,default='/dev/i2c-1',help='I2C device for the power manager')
   parser.add_argument('--module',choices=[1,2,3,4],type=int,default=None,help='Module choice')
   parser.add_argument('--on',action='store_true',help='Turn all modules or the given module on')
   parser.add_argument('--off',action='store_true',help='Turn all modules or the given module off')
   parser.add_argument('--board',choices=[2,3,4],type=int,default=2,help='Board choice')

   args=parser.parse_args()

   pmanager=mm_power_man(args.device,args.board)

   if args.status:
      flags=pmanager.status_flags()
      print("Incoming voltage: %.2fV"%pmanager.input_voltage())
      for module in range(1,5):
         print("Module %d %s"%(module,"ON" if flags["M%d.ENABLED"%module] else "OFF"))
         print("  9V %s %.3fA"%("OK" if flags["M%d.9V_OK"%module] else "OFF",pmanager.current(module,True)))
         #print("  1V8 %s %.3fA"%("OK" if flags["M%d.1V8_OK"%module] else "OFF",pmanager.current(module,False)))
         #print("  9V %s %.3fA %.3fA %.3fA" % ("OK" if flags["M%d.9V_OK" % module] else "OFF",pmanager.current(module, True),pmanager.voltage_temp(module, False),pmanager.voltage_temp(module,True)))
       


   if args.on or args.off:
      if args.module is None:
         pmanager.set_enabled(enabled=args.on)
      else:
         pmanager.set_enabled(imodule=args.module,enabled=args.on)
