import pickle


class message():
    def __init__(self, message, pid, other=""):
        self.command = message
        self.BallotNum = None
        self.AcceptNum = None
        self.AcceptVal = None
        self.val = None
        self.operation = None
        self.other = other
        self.senderPID = pid

    def getReadyToSend(self):
        return pickle.dumps(self)
