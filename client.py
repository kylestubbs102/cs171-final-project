import socket
import sys
import threading
import os
import time
import json
from datetime import datetime

servers = []
serverListeners = []
configData = None
clientSock = None
clientPID = None


def doExit():
    print('do exit')


def userInput():
    while True:
        x = input()

        commandList = x.split(" ")
        command = commandList[0].strip()
        if(command == 'connect'):
            threading.Thread(target=connectToServers).start()

        elif(command == 'sendall'):
            for sock in servers:
                test = "testing from client " + str(clientPID)
                sock[0].sendall(test.encode())
        elif(command == 'send'):
            pid = commandList[1]
            test = "testing individual from client " + str(clientPID)
            test = test.encode()
            for sock in servers:
                if(sock[1] == str(pid)):
                    sock[0].sendall(test)
        elif(command == 'exit'):

            doExit()


def onNewServerConnection(serverSocket, addr):
    serverListeners.append(serverSocket)
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    while True:
        try:
            msg = serverSocket.recv(2048).decode()
        except socket.error:
            serverSocket.close()
        if not msg:
            serverSocket.close()
        if (msg != ''):
            print(msg)


def watch():
    global clientSock
    clientSock = socket.socket()
    clientSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    clientSock.bind((socket.gethostname(), configData[sys.argv[1]]))
    clientSock.listen(32)
    while True:
        c, addr = clientSock.accept()
        threading.Thread(target=onNewServerConnection,
                         args=(c, addr)).start()


def connectToServers():
    print("connect here")
    # connect to servers here, afterwards set up bind
    # put connections in array
    for i in range(1, 6):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((socket.gethostname(), configData[str(i)]))
        msg = 'client ' + str(clientPID)
        sock.sendall(msg.encode())
        servers.append([sock, str(i)])
        # threading.Thread(target=watch).start()


def main():
    global configData
    global clientSock
    global clientPID
    f = open('config.json')
    configData = json.load(f)
    f.close()

    clientPID = sys.argv[1]

    # clientSock
    # initialize clientSock to a connecting socket
    # clientSock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    # clientSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        threading.Thread(target=userInput).start()
        # threading.Thread(target=connectToServers).start()

        threading.Thread(target=watch).start()
    except Exception as error:
        print(error, flush=True)
    while True:
        try:
            pass
        except KeyboardInterrupt:
            print('doExit here')


if __name__ == "__main__":
    main()
