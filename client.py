from server import connectToServers
import socket
import sys
import threading
import os
import time
import json
from datetime import datetime

servers = []
configData = None
clientSock = None


def connectToServers():
    print("connect here")
    # connect to servers here, afterwards set up bind
    # put connections in array


def main():
    global configData
    global clientSock
    f = open('config.json')
    configData = json.load(f)
    f.close()

    # clientSock
    # initialize clientSock to a connecting socket

    threading.Thread(target=connectToServers).start()


if __name__ == "__main__":
    main()
