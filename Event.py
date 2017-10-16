import datetime

class Event:
    """
    Base class for Event instance
    """
    def __init__(self, op, time, node, content):
        self.op = op 
        self.time = time
        self.node = node 
        self.content = content
        self.utc = datetime.datetime.utcnow()