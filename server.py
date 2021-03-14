import socket
import sys
import threading
import os
import time
import json
import pickle
from utility import message, compareBallots
from queue import Queue
from blockchain import blockchain
from datetime import datetime

otherServers = []                 # array of [socket, id(str)]
serverSock = None                 # serverSocket
serverPID = None                  # server's own PID from args(str)
configData = None                 # json config data
lock = threading.Lock()           # lock
failedLinks = set()               # set containing failed links
otherClients = []

hintedLeader = None

receivedACK = False
# delay for sending messages
delay = 2

# data structures
bc = None
OPqueue = Queue()
keyvalue = {}

# paxos variables
BallotNum = [0, 0, 0]      # order: <seq_num, pid, depth>
AcceptNum = [0, 0, 0]
AcceptVal = None
myVal = None
receivedPromises = []
receivedAccepted = []
numReceivedPromises = 0
numReceivedAccepted = 0
requestingClient = None
requestingServer = None
alreadySentAccepted = False


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
    global numReceivedPromises
    global numReceivedAccepted
    global receivedPromises
    global receivedAccepted
    global hintedLeader
    global receivedACK
    # handle messages from other clients
    print(f'{datetime.now().strftime("%H:%M:%S")} connection from', addr)
    serverSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    while True:
        try:
            msg = serverSocket.recv(2048)
        except socket.error:
            serverSocket.close()
        if not msg:
            serverSocket.close()
        if(msg != b''):
            msg = pickle.loads(msg)
            print(
                f'{datetime.now().strftime("%H:%M:%S")} message from {addr}:', msg.command)

            if((msg.command == 'get' or msg.command == 'put') and hintedLeader == serverPID):
                OPqueue.put([msg.other, msg.senderPID, msg.val])
                if(myVal == None):
                    threading.Thread(target=sendAcceptMessages,
                                     args=(True,)).start()

            if(msg.command == 'accept'):
                threading.Thread(target=handleAcceptCommand, args=(
                    msg.BallotNum, msg.val)).start()

            if(msg.command == 'accepted'):
                lock.acquire()
                numReceivedAccepted += 1
                receivedAccepted.append(msg)

                if(numReceivedAccepted >= 2 and not alreadySentAccepted):
                    threading.Thread(target=receiveMajorityAccepted).start()
                lock.release()

            if(msg.command == 'decide' and msg.senderPID == hintedLeader):
                threading.Thread(target=handleDecideCommand, args=(
                    msg.BallotNum, msg.val)).start()

            if(msg.command == 'leader'):
                threading.Thread(target=handleLeaderCommand).start()

            if(msg.command == 'hintedLeader'):
                lock.acquire()
                hintedLeader = msg.senderPID
                lock.release()

            if(msg.command == 'prepare'):
                threading.Thread(target=handlePrepareCommand, args=(
                    msg.BallotNum,)).start()

            if(msg.command == 'promise'):
                lock.acquire()
                numReceivedPromises += 1
                receivedPromises.append(msg)

                # handles the case of all four servers responding
                # server will start two threads total (receives) ???? need to think more about
                if(numReceivedPromises >= 2 and (hintedLeader == None or hintedLeader != serverPID)):
                    threading.Thread(target=receiveMajorityPromises).start()
                lock.release()

            if(msg.command == 'ack'):
                receivedACK = True

    serverSocket.close()


def receiveMajorityPromises():
    global hintedLeader
    global myVal
    global AcceptVal
    global AcceptNum
    global BallotNum
    global receivedPromises
    global numReceivedPromises

    notAllBottom = False
    # think about logic for setting myVal
    for promise in receivedPromises:
        if promise.AcceptVal != None:
            notAllBottom = True
    if(notAllBottom):
        highestBallotMsg = receivedPromises[0]
        for promise in receivedPromises:
            if(compareBallots(promise.AcceptNum, highestBallotMsg.AcceptNum)):
                highestBallotMsg = promise
        AcceptNum = highestBallotMsg.AcceptNum
        myVal = highestBallotMsg.AcceptVal
    else:
        AcceptNum = BallotNum
        # compare ballots function
        # keep trying

    hintedLeader = serverPID
    numReceivedPromises = 0

    msg = message("hintedLeader", serverPID).getReadyToSend()
    time.sleep(delay)
    broadcastToOtherServers(msg)
    for sock in otherClients:
        try:
            sock[0].sendall(msg)
        except socket.error:
            sock[0].close()

    # start Phase 2 if myVal != None
    # start a thread
    if(myVal != None or not OPqueue.empty()):
        threading.Thread(target=sendAcceptMessages, args=(False,)).start()
        # phase 2 will either start with popping an operation from queue and mining it
        # or use a val gained here


def broadcastToOtherServers(msg):
    global otherServers
    for sock in otherServers:
        if(sock[1] not in failedLinks):
            try:
                sock[0].sendall(msg)
            except socket.error:
                sock[0].close()


def receiveMajorityAccepted():
    global numReceivedAccepted
    global bc
    global keyvalue
    global alreadySentAccepted
    global requestingClient
    global requestingServer

    numReceivedAccepted = 0
    msg = message("decide", serverPID)
    msg.val = myVal
    msg.BallotNum = BallotNum
    alreadySentAccepted = True

    # Add block to block chain
    # update KV store
    bc.add(myVal, BallotNum[2])
    keyvalue = bc.recreateKV()
    operation = myVal[0].split(" ")
    print("operation", operation)
    print("keyvalue.keys()", keyvalue.keys())
    opCommand = operation[0]

    # Reset paxos vars
    resetPaxosVars()
    print("paxos vars reset")
    time.sleep(delay)

    broadcastToOtherServers(msg.getReadyToSend())

    msg = message("ack", serverPID)
    for sock in otherClients:
        if(sock[1] == requestingClient):
            try:
                sock[0].sendall(msg.getReadyToSend())
            except socket.error:
                sock[0].close()
            infoMsg = message("info", serverPID)
            if(opCommand == "get" and operation[1] in keyvalue.keys()):
                infoMsg.val = keyvalue[operation[1]]
                try:
                    sock[0].sendall(infoMsg.getReadyToSend())
                except socket.error:
                    sock[0].close()
            elif(opCommand == "get" and operation[1] not in keyvalue.keys()):
                infoMsg.val = "key not found"
                try:
                    sock[0].sendall(infoMsg.getReadyToSend())
                except socket.error:
                    sock[0].close()

    for sock in otherServers:
        if(sock[1] == requestingServer):
            try:
                sock[0].sendall(msg.getReadyToSend())
            except socket.error:
                sock[0].close()

    requestingClient = None
    requestingServer = None
    # restart paxos if more operations in queue
    if(not OPqueue.empty() and myVal == None):
        print("restart paxos from phase 2")
        sendAcceptMessages(True)


def sendAcceptMessages(startFromPhaseTwo):
    global BallotNum
    global myVal
    global requestingClient
    global requestingServer

    if startFromPhaseTwo:
        BallotNum[0] += 1
    if myVal == None:
        op = OPqueue.get()
        requestingClient = op[1]
        requestingServer = op[2]
        myVal = bc.mine(op[0])
    msg = message("accept", serverPID)
    msg.val = myVal
    msg.BallotNum = BallotNum
    time.sleep(delay)
    broadcastToOtherServers(msg.getReadyToSend())


def handleDecideCommand(newBallotNum, newVal):
    global myVal
    global bc
    global keyvalue
    myVal = newVal
    bc.add(myVal, newBallotNum[2])

    # reset paxos vars
    resetPaxosVars()

    keyvalue = bc.recreateKV()


def handleAcceptCommand(newBallotNum, newVal):
    global BallotNum
    global AcceptVal
    global AcceptNum

    print("newBallotNum", newBallotNum)
    print("BallotNum", BallotNum)
    if (compareBallots(newBallotNum, BallotNum)):
        AcceptNum = newBallotNum
        AcceptVal = newVal
        for sock in otherServers:
            if sock[1] not in failedLinks and sock[1] == hintedLeader:
                msg = message("accepted", serverPID)
                msg.val = AcceptVal
                msg.BallotNum = BallotNum
                time.sleep(delay)
                try:
                    sock[0].sendall(msg.getReadyToSend())
                except:
                    sock[0].close()
                break


def handlePrepareCommand(recBallot):
    global BallotNum
    global AcceptNum
    global AcceptVal

    if(compareBallots(recBallot, BallotNum)):
        time.sleep(delay)
        for sock in otherServers:
            if((int(sock[1]) == int(recBallot[1])) and (str(recBallot[1]) not in failedLinks)):
                lock.acquire()
                promise = "promise"
                promise = message(promise, serverPID)
                promise.BallotNum = BallotNum
                promise.AcceptNum = AcceptNum
                promise.AcceptVal = AcceptVal
                try:
                    sock[0].sendall(promise.getReadyToSend())
                except socket.error:
                    sock[0].close()
                lock.release()


def handleLeaderCommand():
    global BallotNum
    global lock
    lock.acquire()
    BallotNum[0] += AcceptNum[0] + 1
    lock.release()

    time.sleep(delay)
    prepare = message("prepare", serverPID)
    prepare.BallotNum = BallotNum

    broadcastToOtherServers(prepare.getReadyToSend())


def resetPaxosVars():
    global BallotNum
    BallotNum[2] = BallotNum[2] + 1
    BallotNum[0] = 0
    global AcceptNum
    AcceptNum = [0, 0, 0]
    global AcceptVal
    AcceptVal = None
    global myVal
    myVal = None
    global receivedPromises
    receivedPromises = []
    global receivedAccepted
    receivedAccepted = []
    global numReceivedPromises
    numReceivedPromises = 0
    global numReceivedAccepted
    numReceivedAccepted = 0
    global alreadySentAccepted
    alreadySentAccepted = False

    print("BallotNum is reset to ", BallotNum)


def onForwardOperation(msg):
    global receivedACK
    for sock in otherServers:
        if(sock[1] == hintedLeader and sock[1] not in failedLinks):
            msg.val = serverPID
            try:
                sock[0].sendall(msg.getReadyToSend())
            except socket.error:
                sock[0].close()

    time.sleep(15)
    if not receivedACK:
        OPqueue.put([msg.other, msg.senderPID, 0])
        threading.Thread(target=handleLeaderCommand).start()
    else:
        receivedACK = False


def connectToClients():
    global otherClients

    for i in range(6, 9):
        if(i != int(serverPID)):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.connect((socket.gethostname(), configData[str(i)]))
            msg_send = 'server ' + serverPID
            msg_send = message(msg_send, serverPID).getReadyToSend()
            sock.sendall(msg_send)
            otherClients.append([sock, str(i)])


def onNewClientConnection(clientSocket, addr, pid):
    global otherClients
    global OPqueue
    print(f'{datetime.now().strftime("%H:%M:%S")} connection from', addr)
    clientSocket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    while True:
        try:
            msg = clientSocket.recv(2048)
        except socket.error:
            clientSocket.close()
        if not msg:
            clientSocket.close()
        if (msg != b''):
            # Three scenarios for operation receives
            # 1. receive op and no hinted leader (try to become leader)
            # 2. receive op and am hinted leader (start from phase 2)
            # 3. receive op and am not hinted leader (forward to hinted leader with timeout)
            msg = pickle.loads(msg)
            if((msg.command == 'get' or msg.command == 'put') and hintedLeader == None):
                OPqueue.put([msg.other, msg.senderPID, 0])
                threading.Thread(target=handleLeaderCommand).start()
            if((msg.command == 'get' or msg.command == 'put') and hintedLeader != serverPID and hintedLeader != None):
                # NEED A TIMEOUT HERE
                threading.Thread(target=onForwardOperation,
                                 args=(msg,)).start()

            if((msg.command == 'get' or msg.command == 'put') and hintedLeader == serverPID):
                OPqueue.put([msg.other, msg.senderPID, 0])
                if(myVal == None):
                    threading.Thread(target=sendAcceptMessages,
                                     args=(True,)).start()
            if(msg.command == 'leader' and hintedLeader != serverPID):
                threading.Thread(target=handleLeaderCommand).start()
            print(msg.command)


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


def doExit():
    global otherServers
    global serverSock

    sys.stdout.flush()
    serverSock.close()
    for sock in otherServers:
        sock[0].close()
    for sock in otherClients:
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
            send = message(test, serverPID).getReadyToSend()
            broadcastToOtherServers(send)
            for sock in otherClients:
                if(sock[1] not in failedLinks):
                    try:
                        sock[0].sendall(send)
                    except socket.error:
                        sock[0].close()
        elif(command == 'send'):
            pid = commandList[1]
            test = "testing individual from server " + str(serverPID)
            test = message(test, serverPID).getReadyToSend()
            for sock in otherServers:
                if(sock[1] == str(pid) and sock[1] not in failedLinks):
                    try:
                        sock[0].sendall(test)
                    except socket.error:
                        sock[0].close()
            for sock in otherClients:
                if(sock[1] == str(pid) and sock[1] not in failedLinks):
                    try:
                        sock[0].sendall(test)
                    except socket.error:
                        sock[0].close()
        elif(command == 'hintedLeader'):
            print(hintedLeader)
        elif(command == 'failLink'):
            # example: failLink 1 2
            if(commandList[1] == serverPID):
                failedLinks.add(commandList[2])
                print("failedLinks:", failedLinks)
            else:
                print("please enter valid source for server {s}".format(
                    s=serverPID))
        elif(command == 'fixLink'):
            # example: fixLink 1 2
            if(commandList[1] == serverPID):
                failedLinks.remove(commandList[2])
            else:
                print("please enter valid source for server {s}".format(
                    s=serverPID))
        elif(command == 'printBlockchain' or command == 'bc'):
            bc.print()
        elif(command == 'printKVStore' or command == 'kv'):
            print(keyvalue)
        elif(command == 'printQueue' or command == 'q'):
            print(OPqueue.queue)
        elif(command == 'failProcess' or command == 'exit'):
            doExit()


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
