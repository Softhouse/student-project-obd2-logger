from __future__ import division
import OBD_IO
import obd_sensors
import time
import shutil
import os
import datetime
import threading
import platform
import serial
import gps

    

class logger:
    def __init__(self, sessionID, userID):
        time.sleep(12) #LET SLEEP FOR SECURE STARTUP, CAN BE LOWERED
        self.port = "/dev/ttyUSB0"
        self.obd = OBD_IO.OBDPort(self.port, 1, 5)

        
        print("Restarting GPS...")
        os.system("sudo killall gpsd")
        print("OBD connected to: " + self.obd.getPortName())

        if(self.obd.getPortName() == "/dev/ttyUSB0"): ## Connect next ttyUSB to GPS
            os.system("sudo gpsd /dev/ttyUSB1 -F /var/run/gpsd.sock")
        else:
            os.system("sudo gpsd /dev/ttyUSB0 -F /var/run/gpsd.sock")

        time.sleep(5) # LET GPS ESTABLISH FIX

        try: ## IF GPS FAILS TO LOAD, RESTART
            self.session = gps.gps("localhost", "2947")
        except:
            os.system("sudo killall gpsd")
            if(self.obd.getPortName() == "/dev/ttyUSB0"):
                os.system("sudo gpsd /dev/ttyUSB1 -F /var/run/gpsd.sock")
            else:
                os.system("sudo gpsd /dev/ttyUSB0 -F /var/run/gpsd.sock")
            self.session = gps.gps("localhost", "2947")
        self.session.stream(gps.WATCH_ENABLE | gps.WATCH_NEWSTYLE)
        
        self.UID = userID
        self.sessionID = sessionID + 1
        self.nrOfResponses = 0
        self.timeGone = 0
        self.seq = ""
        self.startLogging()
    def timestamp(self, format):
         ts = time.time()
         if format == 2:
            st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S:%f')[:-4]
         elif format == 1:
            st = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H.%M.%S')
         return st  
    def pidsSupported(self):
        print("Retrieving supported pids...\n")
        carSens = self.obd.get_sensor_value(obd_sensors.SENSORS[0])
        print(carSens+"\n")
        for i in range (31):
            if carSens[i] == "1":
                print(obd_sensors.SENSORS[i+1].name + ":    IS SUPPORTED")
            else:
                print(obd_sensors.SENSORS[i+1].name + ":    NOT SUPPORTED")
        return carSens

    def writePidToFile(self, command, result):
        self.seq += "[" + command + "," + result + "]"
    def getDTC(self):
        self.obd.send_command("0101")
        nrOfDTC = self.obd.nrOfDTC(self.obd.get_result())
        print(nrOfDTC)
        if nrOfDTC != "NODATA":
            self.obd.send_command("03")
            dtc = self.obd.interpret_DTCresult( self.obd.get_result() )
            dtcCodes = (OBD_IO.decrypt_dtc_code(dtc, nrOfDTC))
            for i in range (int(nrOfDTC)):
                print("Engine DTC errorcode: " + dtcCodes[i] )
                self.writePidToFile("ERROR", dtcCodes[i])
            file.write(self.seq + "-\n")
            time.sleep(5)
    def loadGPSFIX(self):
        for i in range (5):
            report = self.session.next()
            print (report)
            if report['class'] == 'TPV':
                if hasattr(report, 'time'):
                    lon = ("longitude: " + str(report.lon))
            self.session.fix.longitude
            print("Setting up GPS...")
    def startLogging(self):
        iatTimer = 0
        coolTimer = 0
        sessionF = open("session.txt", "w")
        sessionF.write(str(self.sessionID))
        sessionF.close()
        semiSession = 0
        nrOfReq = 0

        carSens = self.pidsSupported()  #GET SUPPORTED PIDS
        temptime = -1

        self.loadGPSFIX()

        startTime = time.time()
        coolTemp = self.obd.get_sensor_value(obd_sensors.SENSORS[5]) #coolant temprature update every 8s
        iatSensor = self.obd.get_sensor_value(obd_sensors.SENSORS[14]) #intake air temprature update every 5s
        while 1:
            self.timeGone = int(((time.time())-startTime)) #Current time - starting time
            filename = "Session_" + str(self.sessionID) + "_" + str(semiSession) + ".txt"
            file = open(filename, "w")
            if self.timeGone>temptime:  #If seconds changes
                self.writePidToFile("UID", self.UID)         #RASPBERRY SERIAL (UNIQE ID) CHANGE THIS LATER 
                self.seq += "+\n"
                self.writePidToFile("SID", str(self.sessionID))
                self.seq += "+\n"

                self.obd.send_command("0101")
                nrOfDTC = self.obd.nrOfDTC(self.obd.get_result())
                print(nrOfDTC)
                
                if nrOfDTC != "NODATA":
                    self.obd.send_command("03")
                    dtc = self.obd.interpret_DTCresult( self.obd.get_result() )
                    dtcCodes = (OBD_IO.decrypt_dtc_code(dtc, nrOfDTC))
                    for i in range (int(nrOfDTC)):
                        print("Engine DTC errorcode: " + dtcCodes[i] )
                        self.writePidToFile("ERROR", dtcCodes[i])
                self.seq += "+\n"

                while nrOfReq < 10:
                    self.timeGone = int(((time.time())-startTime)) #Current time - starting time
                    if self.timeGone>temptime:
                        self.writePidToFile("TIME", self.timestamp(2))
                        self.writePidToFile("GPS", (str(self.session.fix.latitude) + "-" + str(self.session.fix.longitude)))
                        self.session.next()

                        ## MOST IMPORTANT PIDS (RPM, SPEED, MAF, IAT) ##
                        sensorvalue = self.obd.get_sensor_value(obd_sensors.SENSORS[12]) #rpm
                        self.writePidToFile("010C", str(sensorvalue))
                        sensorvalue = self.obd.get_sensor_value(obd_sensors.SENSORS[13]) #speed
                        self.writePidToFile("010D", str(sensorvalue))
                        ## MAF - NOT ALL VECHICLE SUPPORT    -  GET SUPPORT FOR NON-MAF VECHICLES  -  IMAP = RPM * MAP / IAT  -  MAF = (IMAP/120)*(VE/100)*(ED)*(MM)/(R)
                        if(carSens[15] == "1"):
                            sensorvalue = self.obd.get_sensor_value(obd_sensors.SENSORS[16]) #maf
                            self.writePidToFile("0110", str(sensorvalue))
                            curMAF = sensorvalue
                        if iatTimer == 3:
                                iatSensor = self.obd.get_sensor_value(obd_sensors.SENSORS[14]) #intake air temprature update every 3s
                        if(carSens[13] == "1"):
                                self.writePidToFile("010F", str(iatSensor))
                                iatTimer = 0
                        if coolTimer == 7:
                                coolTemp = self.obd.get_sensor_value(obd_sensors.SENSORS[5]) #coolant temprature update every 7s
                        if(carSens[4] == "1"):
                                self.writePidToFile("0105", str(coolTemp))  
                                coolTimer = 0
                        self.seq += "+\n"
                        nrOfReq += 1
                        temptime = self.timeGone
                nrOfReq = 0
                print(self.seq)
                temptime = self.timeGone
                file = open(filename, "a")
                file.write(self.seq)
                file.flush()
                self.seq = ""
                file.close()
                shutil.move("/home/pi/pyOBD_Anif_version/" + filename, "/home/pi/pyOBD_Anif_version/logFiles/" + filename )
                
                self.nrOfResponses += 1
                iatTimer += 1
                coolTimer += 1
                semiSession += 1


