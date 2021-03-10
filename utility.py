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


def compareBallots(BallotOne, BallotTwo):
    if(BallotOne[0] >= BallotTwo[0] and BallotOne[2] >= BallotTwo[2]):
        if(BallotOne[0] == BallotTwo[0]):
            if(BallotOne[1] > BallotTwo[1]):
                return True
            else:
                return False
        else:
            return True
    else:
        return False
