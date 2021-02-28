import socket
import sys
import threading
import os
import time
import json
from queue import Queue
from blockchain import blockchain
from datetime import datetime

otherServers = []                 # array of [socket, id]
serverSock = None
serverPID = None                  # server's own PID from args
configData = None                 # json config data
lock = threading.Lock()           # lock

serverBind = None
otherClients = []

# data structures
bc = None
queue = Queue()
keyvalue = {}


def doExit():
    global otherServers
    global serverSock

    sys.stdout.flush()
    serverSock.close()
    for sock in otherServers:
        sock[0].close()
    os._exit(1)


def userInput():
    while True:
        x = input()
        commandList = x.split(" ")
        command = commandList[0].strip()
        if(command == 'connect'):
            threading.Thread(target=connectToServers).start()
            threading.Thread(target=connectToClients).start()
        elif(command == 'sendall'):
            test = "testing from server " + str(serverPID)
            test = test.encode()
            for sock in otherServers:
                sock[0].sendall(test)
            for sock in otherClients:
                sock[0].sendall(test)
        elif(command == 'send'):
            pid = commandList[1]
            test = "testing individual from server " + str(serverPID)
            test = test.encode()
            for sock in otherServers:
                if(sock[1] == str(pid)):
                    sock[0].sendall(test)
            for sock in otherClients:
                if(sock[1] == str(pid)):
                    sock[0].sendall(test)

        elif(command == 'exit'):
            doExit()


def connectToServers():
    global otherServers

    for i in range(1, 6):
        if(i != int(serverPID)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.connect((socket.gethostname(), configData[str(i)]))
            msg_send = 'server ' + serverPID
            sock.sendall(msg_send.encode())
            otherServers.append([sock, str(i)])


def onNewServerConnection(serverSocket, addr):
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


def connectToClients():
    global otherClients

    for i in range(6, 9):
        if(i != int(serverPID)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.connect((socket.gethostname(), configData[str(i)]))
            msg_send = 'server ' + serverPID
            sock.sendall(msg_send.encode())
            otherClients.append([sock, str(i)])


def onNewClientConnection(clientSocket, addr, pid):
    global otherClients
    clientSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    while True:
        try:
            msg = clientSocket.recv(2048).decode()
        except socket.error:
            clientSocket.close()
        if not msg:
            clientSocket.close()
        if (msg != ''):
            print(msg)


def watch():
    global serverSock
    serverSock = socket.socket()
    serverSock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    serverSock.bind((socket.gethostname(), configData[sys.argv[1]]))
    serverSock.listen(32)
    while True:
        c, addr = serverSock.accept()
        msg_recv = c.recv(2048).decode()
        msgs = msg_recv.split()
        if 'server' in msg_recv:
            threading.Thread(target=onNewServerConnection,
                             args=(c, addr)).start()
        else:
            threading.Thread(target=onNewClientConnection,
                             args=(c, addr, msgs[1])).start()


def main():
    global configData
    global serverPID
    global bc

    if len(sys.argv) != 2:
        print(f'Usage: python {sys.argv[0]} <process_id>')
        sys.exit()

    f = open('config.json')
    configData = json.load(f)
    serverPID = sys.argv[1]
    bc = blockchain(serverPID)
    bc.print()
    # bc.add("put alice 8435928285")
    # bc.add("get alice")
    # bc.add("put bob 8589452")
    # bc.writeToFile()

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
