#!/usr/bin/env python

import client
import sys
import time
import os
from os import listdir
from os import remove
from os.path import isfile, join
time.sleep(7)
os.system("sudo dhclient usb0")
time.sleep(4)
# Server ip
tcp_ip     = '91.123.200.131'
# Dev ip
#tcp_ip     = '127.0.0.1'
tcp_port   = 5005
buffersize = 4096
verbose    = True
l          = ''

while 1:

    # Get the files in the directory "logs"
    #mypath = 'C:/Users/Snif/Documents/Visual Studio 2013/Projects/pyOBD_Anif_version/pyOBD_Anif_version/logFiles'
    mypath = '/home/pi/pyOBD_Anif_version/logFiles'
    #mypath = '/home/jonas/Work/PythonServer_2.0/project-client/logs'
    onlyfiles = [ f for f in listdir(mypath) if isfile(join(mypath,f)) ]

    # If we have files in the folder, upload them
    if len(onlyfiles) > 0:
        connection = client.Client(tcp_ip, tcp_port, buffersize)
        print 'Connecting to the server'
        while 1:
            try:
                connection.connect()
            except:
                time.sleep(3)
                os.system("sudo dhclient usb0")
                time.sleep(3)
                if verbose:
                    e = sys.exc_info()[0]
                    print 'Error: %s' % (e)
                print 'No connection'
                print 'Trying to reconnect...'
                time.sleep(3)
            else:
                break

        print "Connection established to %s:%s" % (str(tcp_ip), str(tcp_port))
        print 'Waiting for connection message'
        print connection.recieve()

        for currentfile in onlyfiles:
            formattedData = {}
            dataEntries = []

             # Files is saved and can now be read
            if os.path.getsize(mypath+"/"+currentfile) > 2:
                with open(mypath+"/"+currentfile, 'r') as f:
                    count = 0
                    for line in f.read().strip().split('+'):
                        # UID - ID code of raspberry
                        if count == 0:
                            line = line.strip().split(']')[0]
                            line = line.strip().split('[')[1]
                            line = line.strip().split(',')[1]
                            formattedData.update({'UID':line})
                            print "UID:%s" % (formattedData['UID'])
                        # Session - ID code of the drivesession
                        elif count == 1:
                      
                            line = line.strip().split(']')[0]
                

                            line = line.strip().split('[')[1]
                            line = line.strip().split(',')[1]
                            formattedData.update({'SESSION':line})
                            print "Session:%s" % (formattedData['SESSION'])
                        # Errors - Stored error-codes
                        elif count == 2:
                            errors = [];
                            multipleLines = line.strip().split(']')
                            multipleLines = multipleLines[0:len(multipleLines)-1]
                            for item in multipleLines:
                                item = item.strip().split('[')[1]
                                item = item.strip().split(',')[1]
                                errors.append(item)
                                print "Error:%s" % (item)
                            formattedData.update({'Errors':errors})
                        # Data entries
                        else:
                            valueHolder = []
                            line = line.strip()
                            if len(line) > 0:
                                line = line.strip().split(']')
                                for key in range(0, len(line)-1):
                                    tempValue = line[key].strip().split('[')[1]
                                    valueHolder.append(tempValue.strip().split(','))
                                dataEntries.append(valueHolder)
                        count += 1

                    UID     = formattedData['UID']
                    session = formattedData['SESSION']

                    # Turn dataEntries into sql to send
                    for lines in dataEntries:
                        datetime = lines[0][1]
                        gps = [lines[1][1].strip().split('-')[0],lines[1][1].strip().split('-')[1]]

                        # If there's no gps-data we do not send them
                        if(gps[0] != "nan" and gps[1] != "nan"):
                            sql = "CALL AddGPS('%s',%s,%s,%s,'%s')" \
                             % (UID,session,gps[0],gps[1],datetime)

                            print "Sending..."
                            connection.send(sql)
                            connection.recieve()

                        for item in range(2, len(lines)):
                            sql = "CALL AddData('%s',%s,'%s',%s,'%s')" % (UID, session, lines[item][0], lines[item][1], datetime)
                            print "Sending..."
                            connection.send(sql)
                            connection.recieve()

                    #Insert error-codes

                    # Start by setting all errors to inactive with procedure WipeError
                    if len(formattedData['Errors']) > 0:
                        sql = "CALL WipeError('%s')" % (UID)
                    
                        print "Sending..."
                        connection.send(sql)
                        connection.recieve()

                        # Now insert each error with a procedure
                        for error in formattedData['Errors']:
                            sql = "CALL AddError('%s','%s')" % (error,UID)
                        
                            print "Sending..."
                            connection.send(sql)
                            connection.recieve()
                    else:
                        print "no errors"
                    f.close()
            remove(mypath+"/"+currentfile)

        connection.send("")
        # Close the connection
        connection.close()
        print "Connection closed"
    else:
        print "No files"
        time.sleep(3)
