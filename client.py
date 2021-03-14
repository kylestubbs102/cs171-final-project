import socket
import sys
import threading
import os
import time
import json
import pickle
import random
from utility import message as m
from datetime import datetime

servers = []
serverListeners = []
configData = None
clientSock = None
clientPID = None
lock = threading.Lock()

hintedLeader = None
receiveACK = False
delay = 15


def doExit():
    global servers
    global clientSock

    sys.stdout.flush()
    clientSock.close()
    for sock in servers:
        sock[0].close()
    os._exit(1)


def userInput():
    while True:
        x = input()

        commandList = x.split(" ", 2)
        command = commandList[0].strip()
        if(command == 'connect'):
            threading.Thread(target=connectToServers).start()
        elif(command == 'sendall'):
            test = "testing from client " + str(clientPID)
            send = m(test, clientPID).getReadyToSend()
            for sock in servers:
                sock[0].sendall(send)
        elif(command == 'send'):
            pid = commandList[1]
            send = m("put", clientPID, commandList[2]).getReadyToSend()
            for sock in servers:
                if(sock[1] == str(pid)):
                    sock[0].sendall(send)
        elif(command == 'sendleader'):
            # example: sendleader 1
            pid = commandList[1]
            message = m("leader", clientPID).getReadyToSend()
            for sock in servers:
                if(sock[1] == str(pid)):
                    sock[0].sendall(message)
        elif(command == 'hintedLeader'):
            print(hintedLeader)
        elif(command == 'exit' or command == 'failProcess'):
            doExit()
        elif(command == 'put' or command == 'get'):
            msg = m(command, clientPID, x)
            threading.Thread(target=onPutOrGetCommand,
                             args=(msg, [hintedLeader])).start()
            # if(hintedLeader == None):
            #     selectedServer = str(random.randint(1, 5))
            #     for sock in servers:
            #         if sock[1] == selectedServer:
            #             sock[0].sendall(msg.getReadyToSend())
            # else:
            #     for sock in servers:
            #         if sock[1] == hintedLeader:
            #             sock[0].sendall(msg.getReadyToSend())


def onPutOrGetCommand(msg, serversTried):
    global hintedLeader
    global receiveACK
    if(hintedLeader == None):
        selectedServer = str(random.randint(1, 5))
        for sock in servers:
            if sock[1] == selectedServer:
                sock[0].sendall(msg.getReadyToSend())
    else:
        for sock in servers:
            if sock[1] == hintedLeader:
                sock[0].sendall(msg.getReadyToSend())
    time.sleep(15)
    print("receivedACK:", receiveACK)
    if not receiveACK:
        for sock in servers:
            if sock[1] not in serversTried:
                serversTried.append(sock[1])
                hintedLeader = sock[1]
                leaderMsg = m("leader", clientPID).getReadyToSend()
                sock[0].sendall(leaderMsg)
                time.sleep(8)
                threading.Thread(target=onPutOrGetCommand,
                                 args=(msg, serversTried)).start()
                break
    else:
        receiveACK = False
        # for sock in servers:
        #     if sock[1] != hintedLeader:
        #         sock[0].sendall(msg.getReadyToSend())
        #         threading.Thread(target=onPutOrGetCommand, args=(msg)).start()
        #         break


def onNewServerConnection(serverSocket, addr):
    global hintedLeader
    global receiveACK
    serverListeners.append(serverSocket)
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    print(f'{datetime.now().strftime("%H:%M:%S")} connection from', addr)
    while True:
        try:
            msg = serverSocket.recv(2048)
        except socket.error:
            serverSocket.close()
        if not msg:
            serverSocket.close()
        if (msg != b''):
            msg = pickle.loads(msg)
            if(msg.command == 'hintedLeader'):
                lock.acquire()
                hintedLeader = msg.senderPID
                lock.release()
            print(msg.command)
            if(msg.command == "info"):
                print("get command result", msg.val)
            if (msg.command == "ack"):
                receiveACK = True


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
    print("connecting to servers")
    # connect to servers here, afterwards set up bind
    # put connections in array
    for i in range(1, 6):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((socket.gethostname(), configData[str(i)]))
        msg = 'client ' + str(clientPID)
        sock.sendall(msg.encode())
        servers.append([sock, str(i)])


def main():
    global configData
    global clientSock
    global clientPID
    f = open('config.json')
    configData = json.load(f)
    f.close()

    clientPID = sys.argv[1]

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
            doExit()


if __name__ == "__main__":
    main()
