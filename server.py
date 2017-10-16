import sys, os, time
import socket
import threading
import pickle
import Event
from dateutil import tz

'''
DECLARATION OF GLOBAL VARIABLES
'''
# Read in from hosts.txt to config NODE_ID and 
# cmd line will be like "python2 server.py hosts.txt 1", which specifies hosts file to open and my_NODE_ID
hosts_file = sys.argv[1]
NODE_ID = int(sys.argv[2])
MY_PORT = 1
count_num = 0
id_ports = {}
destination_ips = {}
with open(hosts_file) as file:
    for line in file:
        count_num += 1
        parsed = line.strip().split(" ")
        id_ports[int(parsed[1])] = int(parsed[3])
        destination_ips[int(parsed[1])] = parsed[2]
        # found my configuration
        
        if int(parsed[1]) == NODE_ID:
            my_IP, MY_PORT = parsed[2], parsed[3]
    print("NODE_ID: ",  NODE_ID, "IP: ", my_IP, "PORT: ", MY_PORT )
    

Lock = threading.Lock()

# Bring back local records if exists for current site
if os.path.isfile(str(NODE_ID) + '_log.p'):
    (PL, blockInformation, tweetInformation, T, clock) = pickle.load(open(str(NODE_ID) + '_log.p', "rb" ))
# Otherwise, initialize as global variables
else:
    # Partial log
    PL = set()
    # Log for recording block information
    blockInformation = set()
    # Log for recording tweet at local 
    tweetInformation = set()
    # 2d time matrix
    # count_num is how many lines are there in the hosts.txt file
    T = [[0 for i in xrange(count_num)] for i in xrange(count_num)] 
    #time
    clock = 0   
            

'''
PREPARE FUNCTIONS
'''


def hasRec(T, event, siteId):
    return T[siteId-1][event.node-1] >= event.time

def get_NE(NP):
    NE = set()
    for a,e in NP:
        if not hasRec(T, e, NODE_ID):
            NE.add((a,e))
    return NE


def exists_unblocked(block, set_events):
    for e in set_events:
        if block[0] == e[0] and block[1] == e[1]:
            return e
    return


def update_blockInformation(NE):
    # print("entered update_blockInformation")
    tmp = set()
    global blockInformation
    block_set = list(blockInformation) + [(int(n.node), int(n.content)) for m,n in NE if n.op == "block"]
    unblock_set = [(int(n.node), int(n.content)) for m,n in NE if n.op == "unblock"]
    
    for e in block_set:
        result = exists_unblocked(e, unblock_set)
        if result is not None:
            unblock_set.remove(result)
            continue
            
        else:
            tmp.add((e[0], e[1]))
            
    blockInformation = tmp
    
    
    
def update_tweetInformation(NE):
    # print("Entered update_tweetInforamtion")
    global tweetInformation
    for a, e in NE:
        if e.op == 'tweet':
            tweetInformation.add(e)
    
    


def update_T(other_NODE_ID, other_T):
    # print("Entered update_T")
    global T
    for k in xrange(count_num):
        T[NODE_ID-1][k] = max(T[NODE_ID-1][k], other_T[other_NODE_ID-1][k])
    for k in xrange(count_num):
        for l in xrange(count_num):
            T[k][l] = max(T[k][l], other_T[k][l])
    

    
def acknowledge_by_other(e):
    for n in xrange(count_num):
        if not hasRec(T, e, n+1):
            return False
    return True
    


def update_PL(NE):
    # print("Entered updated_PL")
    global PL
    PL = set([(a, e) for (a, e) in (PL | NE) if not acknowledge_by_other(e)])
    


def sentMsgToOtherSites():
    '''
    NP = {eR | eR in PL[i] and !hasRec(T[i],eR,j)}
    send msg[i][j], T[i], NP to p[j]
    '''
    
    NP = set()
    sentNodes = set()
    global blockInformation
    global NODE_ID
    # print("entered sentMsgToOtherSites() function")
    for a,e in PL:
        for node in id_ports.keys():
            if node == NODE_ID:
                continue
            if (int(NODE_ID), int(node)) in blockInformation: 
                continue
            if not hasRec(T, e, node):
                NP.add((a, e))
                sentNodes.add(node)
    # print(sentNodes)
    # print(NP)
    for portNum in sentNodes:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #host = socket.gethostname()
        port = id_ports[portNum]
        try:
            sock.connect((destination_ips[portNum], port))
            # Use pickle to unpack this as a set of event records
            msgElem = (NODE_ID, T, NP)
            msg = pickle.dumps(msgElem)
            sock.send(msg)
            sock.close()
        except socket.error as e:
            print("[Error] Failed to sent event log: %s to site: %d", e, portNum)



def tweet(message, NODE_ID):
    """
    tweet a message
    add tweet event into log and sent message to site j
    if !hasRec(time, event, j)
    """
    #Lock.acquire()
    # print("Entered tweet function")
    global clock
    clock += 1
    T[NODE_ID-1][NODE_ID-1] = clock
    tweetEvent = Event.Event('tweet', clock, NODE_ID, message)
    PL.add(("insert",tweetEvent))
    tweetInformation.add(tweetEvent)
    sentMsgToOtherSites()
    #Lock.release()



def block(NODE_ID, userId):
    """
    block a specific user
    """
    # Input validation
    if int(userId) == NODE_ID:
        print("[Invalid Input] You cannot block yourself!")
    elif int(userId) not in id_ports.keys():
        print("[Invalid Input] No user with user id: " + str(userId))
    elif (NODE_ID, int(userId)) in blockInformation:
        print("[Invalid Input] You have already blocked this user!")
    else:
        global clock
        #Lock.acquire()
        clock += 1
        blockEvent = Event.Event('block', clock, NODE_ID, str(userId))
        T[NODE_ID-1][NODE_ID-1] = clock
    
        PL.add(("insert",blockEvent))
        
        global blockInformation
        blockInformation.add((NODE_ID, int(userId)))
        #Lock.release()



def unblock(NODE_ID, userId):
    #input validation
    if int(userId) not in id_ports.keys():
        print("[Invalid Input] No user with userId: " +  userId)
    elif (NODE_ID, int(userId)) not in blockInformation:
        print("[Invalid Input] You didn't block this user")
    elif (NODE_ID, int(userId)) in blockInformation:
        global clock
        clock += 1
        T[NODE_ID-1][NODE_ID-1] = clock
        unblockEvent = Event.Event('unblock', clock, NODE_ID, str(userId))
        
        PL.add(("delete",unblockEvent))
        
        blockInformation.remove((NODE_ID, int(userId)))


def view():
    """
    display timeline of entire set of tweets
    """
    # print("entered view() function")
    for e in sorted(tweetInformation, key=getKey, reverse=True):
    # sort based on time
        # if I'm not blocked by the server who created the event
        central = getKey(e)
        if (e.node, NODE_ID) not in blockInformation and e.op == "tweet":
            print("Server: {}, Tweet msg: {}, Local time: {}\n".format(e.node, e.content, central))

def getKey(item):
    utc = item.utc
    from_zone = tz.tzutc()
    to_zone = tz.tzlocal()
    utc = utc.replace(tzinfo=from_zone)
    central = utc.astimezone(to_zone)
    return central    


    
def showPL():
    for pl in PL:
        print("Type: {}, Server: {},  Operation: {},  Content: {}, UTC time: {}\n".format(pl[0], pl[1].node, pl[1].op, pl[1].content, pl[1].time))


def showT():
    for i in range(count_num):
        print(T[i])
    # print(T)


def show_lockInformation():
    print(blockInformation)
 
    
def print_message(threadName, message):
    print (threadName, " received: ", message)


class threadRemote(threading.Thread):
    def __init__(self, threadID, name, description):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.description = description

    def process(self, c, addr): 
        c.send('Thank you for connecting')
        message = c.recv(4096).decode("ascii")
        #Lock.acquire()
        
        c.close()
        
        
        
    def run(self):
        print("Starting" + self.name)
        
        remoteSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #host = socket.gethostname()
        remoteSocket.bind(('', int(MY_PORT)))
        remoteSocket.listen(10) #wait for client connection
        while True:
            c, addr = remoteSocket.accept() #Establish connection with client
           
            # Note: once you accept a connection, you need to immediately pass it off to another function (via thread) for parsing
            # This is because your listening thread should not waste time processing information when new packets may come in
            # You can pass the c, addr (socket connection info) to a function. You don't even need to get message before passing
            
            #thread.start_new_thread(self.process,(c,addr,))
            #process_thread = self.process(c,addr)
            #process_thread.start()
            print( 'Got connection from', addr)
            message = c.recv(4096)
            # print(message)
            
            #Lock.acquire()
            
            # Upon receipt, loads pickle
            (other_NODE_ID, other_T, NP) = pickle.loads(message)
            other_NODE_ID = int(other_NODE_ID)
            c.close()
            
            
            # UPON RECEIPT, UPDATE NE, blockInformation, tweetInformation and T
            NE = get_NE(NP)
            # print("NE: ")
            # print(NE)
            
            global blockInformation
            update_blockInformation(NE)
            
            global tweetInformation
            update_tweetInformation(NE)
            
            global T
            update_T(other_NODE_ID, other_T)
            
            global PL
            update_PL(NE)
            
            # Save in local disk
            pickle.dump((PL, blockInformation, tweetInformation, T, clock), open(str(NODE_ID) + '_log.p', "wb" ))

            #Lock.release()
            


class threadLocal(threading.Thread):
    def __init__(self, threadID, name, description):
        threading.Thread.__init__(self)
        self.threadID = threadID
        self.name = name
        self.description = description
    
    def run(self):
        print( "Starting" + self.name)
        #localSocket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        #host = socket.gethostname()
        #localSocket.bind(('', int(MY_PORT)))
        Lock.acquire()
        
        
        
        # Read command line input
        print("Please enter\n\t - tweet your_msg to tweet a message.\
            \n\t - block user_name to block a user.\
            \n\t - unblock user_name to unblock a user.\
            \n\t - view to view all tweets.\
            \n\t - showPL to view partial log.\
            \n\t - showT to view timestamps.\
            \n\t - showBlock to view blockInformation.\
            \n\t - menu to show menu.\
            \n\t - quit to exit.")
            
        while True:
            inputData = raw_input("Please enter the operation: ")
            
            if inputData.strip() == "":
                continue
            
            parsed = inputData.split(" ")
            
            cmd = str(parsed[0]).strip()

            content = " ".join(parsed[1:]) 
            
            if cmd.lower() == "view":
                view()
            
            elif cmd.lower() == "tweet":
                print(content)
                tweet(content, NODE_ID)
            
            elif cmd.lower() == "block":
                block(NODE_ID,content)
            
            elif cmd.lower() == "unblock":
                unblock(NODE_ID, content)
            
            elif cmd.lower() == "showpl":
                showPL()
                
            elif cmd.lower() == "showt":
                showT()
            
            elif cmd.lower() == "showblock":
                show_lockInformation()
            
                
            elif cmd.lower() == "menu":
                print("Please enter\n\t - tweet your_msg to tweet a message.\
                        \n\t - block user_name to block a user.\
                        \n\t - unblock user_name to unblock a user.\
                        \n\t - view to view all tweets.\
                        \n\t - showPL to view partial log.\
                        \n\t - showT to view timestamps.\
                        \n\t - showBlock to view blockInformation.\
                        \n\t - menu to show menu.\
                        \n\t - quit to exit.")
            
            elif cmd.lower() == "quit":
                sys.exit()
            else:
                print("invalid command")
        
        Lock.release()


def main():
    local = threadLocal(1, "threadLocal", "handle local command")
    remote = threadRemote(2, "threadRemote", "handle requests from client")
    local.start()
    remote.start()


if __name__ == "__main__":
    main()



    