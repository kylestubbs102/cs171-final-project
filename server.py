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
failedLinks = set()
serverBind = None
otherClients = []

delay = 2

# data structures
bc = None
queue = Queue()
keyvalue = {}

# paxos variables
BallotNum = [0, 0, 0]      # order: <seq_num, pid, depth>
AcceptNum = [0, 0, 0]
AcceptVal = None


def doExit():
    global otherServers
    global serverSock

    sys.stdout.flush()
    serverSock.close()
    for sock in otherServers:
        sock[0].close()
    os._exit(1)


def userInput():
    global bc

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
        elif(command == 'failLink'):
            # example: failLink 1 2
            failedLinks.add(commandList[2])
        elif(command == 'fixLink'):
            # example: fixLink 1 2
            failedLinks.remove(commandList[2])
        elif(command == 'printBlockchain'):
            bc.print()
        elif(command == 'printKVStore'):
            print(keyvalue)
        elif(command == 'printQueue'):
            print(queue)
        elif(command == 'failProcess'):
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
            if(msg == 'leader'):
                threading.Thread(target=handleLeaderCommand).start()

            command = msg.split(" ")
            if(command[0] == 'prepare'):
                threading.Thread(target=handlePrepareCommand, args=(
                    command[1], command[2], command[3])).start()

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
    print(f'{datetime.now().strftime("%H:%M:%S")} connection from', addr)
    clientSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    while True:
        try:
            msg = clientSocket.recv(2048).decode()
        except socket.error:
            clientSocket.close()
        if not msg:
            clientSocket.close()
        if (msg != ''):
            if(msg == 'leader'):
                threading.Thread(target=handleLeaderCommand).start()
            print(msg)


def handlePrepareCommand(seqNum, pid, depth):
    global BallotNum
    global AcceptNum
    global AcceptVal

    seqNum = int(seqNum)
    pid = int(pid)
    depth = int(depth)
    if seqNum >= BallotNum[0] and depth >= BallotNum[2]:
        send = True
        if(seqNum == BallotNum[0] and (int(BallotNum[0]) > int(pid))):
            send = False
        if(send):
            time.sleep(delay)
            for sock in otherServers:
                if(int(sock[1]) == int(pid) and (int(pid) not in failedLinks)):
                    promise = "promise "
                    # TEMP CODE
                    promise += str(serverPID)
                    # promise.join(BallotNum)
                    # promise.join(AcceptNum)
                    # promise.join(AcceptVal)
                    sock[0].sendall(promise.encode())


def handleLeaderCommand():
    global BallotNum
    BallotNum[0] += 1

    time.sleep(delay)
    for sock in otherServers:
        # sock [socket, pid]
        if(sock[1] not in failedLinks):
            promise = "prepare {seq} {pid} {depth}".format(
                seq=BallotNum[0], pid=BallotNum[1], depth=BallotNum[2])

            sock[0].sendall(promise.encode())


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
    global keyvalue

    global BallotNum

    if len(sys.argv) != 2:
        print(f'Usage: python {sys.argv[0]} <process_id>')
        sys.exit()

    f = open('config.json')
    configData = json.load(f)
    serverPID = sys.argv[1]
    bc = blockchain(serverPID)
    keyvalue = bc.recreateKV()

    BallotNum[1] = int(serverPID)

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
