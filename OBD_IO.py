import serial
import string
import time
from math import ceil
from datetime import datetime

import obd_sensors
from obd_sensors import hex_to_int

GET_DTC_COMMAND   = "03"
CLEAR_DTC_COMMAND = "04"
GET_FREEZE_DTC_COMMAND = "07"

##Should be placed in loggerfile
def decrypt_dtc_code(code, nrOfDTC):
    """Returns the 5-digit DTC code from hex encoding"""
    dtc = []
    current = code
    type = ""
    newRow = 0
    if nrOfDTC != "NODATA":
        for i in range(0,nrOfDTC):
            if len(current)<4:
                print( "Tried to decode bad DTC: " + str(code))

            tc = obd_sensors.hex_to_int(current[0]) #typecode
            tc = tc >> 2
            if   tc == 0:
                type = "P"
            elif tc == 1:
                type = "C"
            elif tc == 2:
                type = "B"
            elif tc == 3:
                type = "U"
            else:
                print("raise tc")

            dig1 = str(obd_sensors.hex_to_int(current[0]) & 3)
            dig2 = str(obd_sensors.hex_to_int(current[1]))
            dig3 = str(obd_sensors.hex_to_int(current[2]))
            dig4 = str(obd_sensors.hex_to_int(current[3]))
            dtc.append(type+dig1+dig2+dig3+dig4)
            newRow+=1
            if newRow < 3:
                current = current[4:]
            else:
                current = current[6:]
                newRow=0
    return dtc

class OBDPort:
     """ OBDPort abstracts all communication with OBD-II device."""
     def __init__(self,portnum,SERTIMEOUT,RECONNATTEMPTS):
         """Initializes port by resetting device and gettings supported PIDs. """
         baud     = 38400
         databits = 8
         par      = serial.PARITY_NONE  # parity
         sb       = 1                   # stop bits
         to       = SERTIMEOUT
         self.ELMver = "Unknown"
         self.State = 1 #state SERIAL is 1 connected, 0 disconnected (connection failed)
         self.port = None
         self.portname = portnum
         self.faultCounter = 0
         print("PORT :                  " + self.portname)
         print("Opening serial port...")
         try:
             self.port = serial.Serial(portnum,baud, \
             parity = par, stopbits = sb, bytesize = databits,timeout = to)
         except serial.SerialException as e:
             print (e)
             self.State = 0
             self.close()
             time.sleep(2)
             self.__init__(self.portname, 1, 7)
             return None
         print("Interface successfully " + self.port.portstr + " opened")

         print("Connecting to ECU...")
         try: 
            self.send_command("atz")   # initialize
            time.sleep(3)
         except serial.SerialException:
            print("Failed sending ATZ command.\nReconnecting...")
            time.sleep(2)
            self.State = 0
            self.close()
            self.__init__(self.portname, 1, 7)
            return None

         self.ELMver = self.get_result()
         if(self.ELMver is None):
             print("- THIS IS NOT AN USB ELM-DEVICE - \nChanging port....")
             if(self.port.name == "/dev/ttyUSB0"):
                try:
                    print("Trying port ttyUSB1...")
                    self.port = serial.Serial("/dev/ttyUSB1",baud, \
                    parity = par, stopbits = sb, bytesize = databits,timeout = to)
                except serial.SerialException:
                    #self.State = 0
                    self.close()
                    print("NO OR ONLY GPS-USB ATTACHED... PLEASE ATTACH ELM327-DEVICE...")
                    self.__init__(self.portname, 1, 7)
             elif(self.port.name == "/dev/ttyUSB1"):
                try:
                    print("Trying port ttyUSB0")
                    self.port = serial.Serial("/dev/ttyUSB0",baud, \
                    parity = par, stopbits = sb, bytesize = databits,timeout = to)
                except serial.SerialException:
                    #self.State = 0
                    self.close()
                    print("NO CORRECT OR ONLY GPS-USB ATTACHED...\nPLEASE MAKE SURE ELM327-DEVICE IS ATTACHED...")
                    self.__init__(self.portname, 1, 7)
         print("atz response:" + str(self.ELMver))
         self.send_command("ate0")  # echo off
         print("ate0 response:" + str(self.get_result()))
         self.send_command("0100")
         ready = self.get_result()
         
         print("ready: " + str(ready))
         if(ready == None):
             self.close()
             self.__init__(self.portname, 1, 7)
         
         if (str(ready) == ""):
             ready = "EMPTY BUFFERT"

         while(str(ready[0]) != "4"):
            if self.faultCounter == 20:
                self.close()
                self.__init__(self.portname, 1, 7)
            print("Ready[0], Bad read: " + str(ready[0]))
            if(str(ready[0]) == "S"):
                print("PLEASE RECONNECT ELM327-DEVICE")
                time.sleep(2)
            print("Resending command (0100) \"Pids Supported\" ...")
            self.send_command("0100")
            ready = self.get_result()
            print(ready)
            self.faultCounter += 1
         return None            
     def close(self):
         """ Resets device and closes all associated filehandles"""
         if (self.port!= None) and self.State==1:
            self.send_command("atz")
            self.port.close()
         self.port = None
         self.ELMver = "Unknown"
     def send_command(self, cmd):
         """Internal use only: not a public interface"""
         if self.port:
             self.port.flushOutput()
             self.port.flushInput()
             for c in cmd:
                 self.port.write(c)
             self.port.write("\r\n")
     def interpret_result(self,code):
         """Internal use only: not a public interface"""
         # Code will be the string returned from the device.
         # It should look something like this:
         # '41 11 0 0\r\r'
         # 9 seems to be the length of the shortest valid response
         if len(code) < 7:
             #raise Exception("BogusCode")
             print ("Bad code: " + str(code))
         # get the first thing returned, echo should be off
         code = string.split(code, "\r")
         code = code[0]
         # remove whitespace
         code = string.split(code)
         code = string.join(code, "")
         #cables can behave differently 
         if code[:6] == "NODATA": # there is no such sensor
             return "NODATA"
         # first 4 characters are code from ELM
         code = code[4:]
         return code
     def interpret_DTCresult(self,code):
         if len(code) < 7:
             print ("Bad code")+code
         # get the first thing returned, echo should be off
         code = string.split(code, "\r")
         code = code[0]
         #remove whitespace
         code = string.split(code)
         code = string.join(code, "")
         #cables can behave differently 
         if code[:6] == "NODATA": # there is no such sensor
             return "NODATA"
         # first 4 characters are code from ELM
         code = code[2:]
         return code
     def nrOfDTC(self,code):
         if len(code) < 7:
             print ("Bad code" + str(code))
         # get the first thing returned, echo should be off
         code = string.split(code, "\r")
         code = code[0]
         #remove whitespace
         code = string.split(code)
         code = string.join(code, "")
         #cables can behave differently 
         if code[:6] == "NODATA": # there is no such sensor
             return "NODATA"
             
         # first 4 characters are code from ELM
         code = code[4:6]
         nr = int(code, 16) - 128
         return nr
     def get_result(self):
         """Internal use only: not a public interface"""
         #time.sleep(0.01)
         repeat_count = 0
         counter = 0
         c = "" # new
         newPort = ""
         if self.port is not None:
             buffer = ""
             while 1:
                 if(counter == 50):
                     if(self.portname == "/dev/ttyUSB0"):
                         newPort = "/dev/ttyUSB1"
                     elif(self.portname == "/dev/ttyUSB1"):
                         newPort = "/dev/ttyUSB0"
                     self.close()
                     self.__init__(newPort, 1, 7)
                     return "0--"
                     break;
                 try:
                    c = self.port.read(1)
                 except:
                    self.close()
                    print("Reading problems...")
                    self.__init__(self.portname, 1, 7)
                 #print("output: " + c)
                 #print("data output: " + c)
                 if len(c) == 0:
                    if(repeat_count == 10):
                        self.close()
                        self.__init__("/dev/ttyUSB0", 1, 7)
                        return "1--"
                        break
                    print ("NO DATA RECIEVED!\n")
                    repeat_count = repeat_count + 1
                    continue
                    
                 if c == '\r':
                    continue
                    
                 if c == ">":
                    break;
                     
                 if buffer != "" or c != ">": #if something is in buffer, add everything
                    buffer = buffer + c
                 counter += 1

             if(buffer == ""):
                print("buffer is empty")

             return buffer
         else:
            print("PORT NOT CONNECTED...")
         return "2--"
     # get sensor value from command
     def get_sensor_value(self,sensor):
         """Internal use only: not a public interface"""
         cmd = sensor.cmd
         self.send_command(cmd)
         data = self.get_result()
         
         if data:
             data = self.interpret_result(data)
             if data != "NODATA":
                 data = sensor.value(data)
         else:
             return "NORESPONSE"
             
         return data
     # return string of sensor name and value from sensor index
     def sensor(self , sensor_index):
         """Returns 3-tuple of given sensors. 3-tuple consists of
         (Sensor Name (string), Sensor Value (string), Sensor Unit (string) ) """
         sensor = obd_sensors.SENSORS[sensor_index]
         r = self.get_sensor_value(sensor)
         return (sensor.name,r, sensor.unit)
     def sensor_names(self):
         """Internal use only: not a public interface"""
         names = []
         for s in obd_sensors.SENSORS:
             names.append(s.name)
         return names              
     def getPortName(self):
         portname = self.port.portstr
         return portname