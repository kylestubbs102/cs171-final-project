import socket
import sys
import threading
import os
import time
import json
from datetime import datetime

otherServers = []                 # array of [socket, id]
serverSock = None
serverPID = None                  # server's own PID from args
configData = None                 # json config data
lock = threading.Lock()           # lock


def doExit():
    global otherServers
    global serverSock

    sys.stdout.flush()
    serverSock.close()
    for sock in otherServers:
        sock[0].close()
    os._exit(1)


def userInput():
    global activeRequest

    while True:
        x = input()

        commandList = x.split("'", 1)
        command = commandList[0].strip()
        if(command == 'connect'):
            threading.Thread(target=connectToServers).start()
        elif(command == 'send'):
            for sock in otherServers:
                test = "testing from server " + str(serverPID)
                test = test.encode()
                sock[0].sendall(test)
        elif(command == 'exit'):
            doExit()


def connectToServers():
    global otherServers

    otherServers = []
    for i in configData:
        if(i != serverPID):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.connect((socket.gethostname(), configData[i]))
            otherServers.append([sock, str(i)])


def onNewClientConnection(serverSocket, addr):
    # handle messages from other clients
    print(f'{datetime.now().strftime("%H:%M:%S")} connection from', addr)
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    while True:
        try:
            msg = serverSocket.recv(64).decode()
        except socket.error:
            serverSocket.close()
        if not msg:
            serverSocket.close()
        if(msg != ''):
            print(f'{datetime.now().strftime("%H:%M:%S")} message from {addr}:', msg)

    serverSocket.close()


def watch():
    global serverSock
    serverSock = socket.socket()
    serverSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serverSock.bind((socket.gethostname(), configData[sys.argv[1]]))
    serverSock.listen(32)
    while True:
        c, addr = serverSock.accept()
        threading.Thread(target=onNewClientConnection,
                         args=(c, addr)).start()


def main():
    global configData
    global serverPID
    if len(sys.argv) != 2:
        print(f'Usage: python {sys.argv[0]} <process_id>')
        sys.exit()

    f = open('config.json')
    configData = json.load(f)
    serverPID = sys.argv[1]
    # print(configData[clientPID])

    try:
        # user input thread
        threading.Thread(target=userInput).start()

        # watch for other client connections
        threading.Thread(target=watch).start()

    except Exception as error:
        print(error, flush=True)

    f.close()
    while True:
        try:
            pass
        except KeyboardInterrupt:
            doExit()


if __name__ == "__main__":
    main()
