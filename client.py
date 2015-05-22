#!/usr/bin/env python

import socket


class Client(object):

    #
    # @params
    # TCP_IP      -- IP of the target we want to connect to
    # TCP_PORT    -- Port of the target we want to connect to
    # BUFFER_SIZE -- Our buffersize for receiving data
    #
    def __init__(self, TCP_IP, TCP_PORT, BUFFER_SIZE):
        self.TCP_IP      = TCP_IP
        self.TCP_PORT    = TCP_PORT
        self.BUFFER_SIZE = BUFFER_SIZE
        self.ANSWERS     = []
        self.s           = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    #
    # Setup the connection with our socket
    #
    def connect(self):
        self.s.connect((self.TCP_IP, self.TCP_PORT))

    #
    # Send given message through the connection
    #
    def send(self, MESSAGE):
        sentData = self.s.send(MESSAGE)
        return sentData

    #
    # Recieve data from the connected socket
    # to self.ANSWER and return the recieved
    # data.
    #
    def recieve(self,size=None):
        if size is None:
            size = self.BUFFER_SIZE

        data = self.s.recv(size)
        self.ANSWERS.append(data)
        return str(data)

    #
    # Close the connected socket
    #
    def close(self):
        self.s.close()
