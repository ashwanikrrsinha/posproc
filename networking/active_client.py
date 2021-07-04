import socket
from constants import *
from pyngrok import ngrok
import threading
"""
This module contains code for active client who is going to be doing all the computation.
In theory we consider bob to be the active client who asks question to alice about parity
and Alice is an passive client who is just going to reply to all the questions that bob
asks.
"""


def parity_of_indexes(raw_key, indexes):
    #TODO: Include this method in the PassiveClient Class.
    s = 0
    for i in indexes:
        s += raw_key[i]
    return s % 2

class Client(socket.socket):    
    def send_a_message_to_server(self, message:str) -> None:
        """
        Bob sends a message to the server i.e. Alice 

        Args:
            message (str): The message to be sent in the form of a string.
        """
        msg_length = len(message)
        send_length = str(msg_length)
        send_length += " "*(HEADER - len(send_length))
        self.send(send_length.encode(FORMAT))
        self.send(message.encode(FORMAT))

    def receive_a_message_from_server(self) -> str:
        """
        Bob can receive a message from server i.e. Alice.

        Returns:
            message (str): The message received from the Server i.e. Alice.
        """
        msg_length = self.recv(HEADER).decode(FORMAT)
        if msg_length:
            try:
                msg_length = int(msg_length)
                message = self.recv(int(msg_length)).decode(FORMAT)
                return message
            except:
                if msg_length == ' ':
                    print("Invalid Literal for int") # TODO : fix this error!
    
    def send_a_message_to_the_client(self, client, message:str) -> None:
        """
        Alice (Server) can send a message to Bob(Client).

        Args:
            client (ActiveClient): The client who is going to receive message i.e. Bob.
            message (str): The message to be sent to Bob.
        """
        msg_length = len(message)
        send_length = str(msg_length)
        send_length += " "*(HEADER - len(send_length))
        client.send(send_length.encode(FORMAT))
        client.send(message.encode(FORMAT))
    
    def receive_a_message_from_client(self, client) -> str:
        """
        Alice (Server) can receive a message from Bob (Client)

        Args:
            client (ActiveClient): The client who is going to send the message i.e. Bob.

        Returns:
            message (str): The message received from Bob(Client)
        """
        msg_length = client.recv(HEADER).decode(FORMAT)
        if msg_length:
            try:
                msg_length = int(msg_length)
                message = client.recv(int(msg_length)).decode(FORMAT)
                return message
            except:
                if msg_length == ' ':
                    print("Blank Message!")  # TODO : fix this error!
    
    def start_ngrok_tunnel(self, port):
        """
        NGROK tunnel is used for port forwarding the ngrok address to the local address

        Args:
            port (int): Local Port which is to be used for forwarding. 
                        (Use the port that is not already being used by your system.)
        Returns:
            public_addr (tuple): This is what a public pc can use to connect to this Server.
                                 This is a pair (PUBLIC_IP, PUBLIC_PORT)
        """
        tunnel = ngrok.connect(port, "tcp")
        url = tunnel.public_url.split("://")[1].split(":")
        ip = socket.gethostbyaddr(url[0])[-1][0]
        public_addr = (ip, int(url[1]))
        return public_addr


class PassiveClient(socket.socket):
    """
    Creates the Server (Alice's) socket    

    Args:
        correct_key (list): Alice's Key Obtained from the protocol
        socket ([type]): [description]
        socket ([type]): [description]
    """
    def __init__(self, correct_key:list, server_type=LOCAL_SERVER, port=LOCAL_PORT):
        super().__init__()
        
        #This is the correct_key i.e. the Key that Alice has.
        self.__correct_key = correct_key

        self.clients = []
        self.nicknames = []
        

        self.server_type = server_type
        self.port = port

        if server_type == LOCAL_SERVER:
            self.address = (LOCAL_IP, self.port)
        if server_type == PUBLIC_SERVER:
            self.address = self.start_ngrok_tunnel(self.port)

        # The Server will start on this address
        self.LOCAL_ADDRESS = (LOCAL_IP, LOCAL_PORT)
        # Then we can port-forward the ngrok address to this address

        self.start_listening()

        # Now Start accepting connections:
        self.start_receiving()

    def get_address(self):
        return self.address

    def start_listening(self):
        print(f"[STARTING] {self.server_type} server is starting...")
        self.bind(self.LOCAL_ADDRESS)
        self.listen(1)
        print(f"[LISTENING] Server is listening @ {self.get_address()}")

    def handle_client(self, client, address):
        connected = True
        while connected:
            msg_received = self.receive_a_message_from_client(client)
            if msg_received:
                print(f"[Client @ {address}]: {msg_received}")
                if msg_received.startswith("ask_parity"):
                    msg_to_send = self.ask_parity_return_message(msg_received)
                    self.send_a_message_to_the_client(client, msg_to_send)

    def ask_parity_return_message(self, msg_received: str):
        splitted_parity_msg = msg_received.split(":")
        msg_no = int(splitted_parity_msg[1])
        indexes_o = splitted_parity_msg[2].split(",")
        indexes = []
        for i in indexes_o:
            indexes.append(int(i))
        #indexes contains the indexes of bits to calculate parities!
        # Assuming Alice is the instance of this Server Class
        parity = parity_of_indexes(self.alices_key, indexes)
        msg_to_send = f"ask_parity:{msg_no}:{parity}"
        return msg_to_send

    def start_receiving(self):
        while True:
            client, addr = self.accept()
            #client.address = addr
            #self.clients.append(client)
            print(f"Connected with {addr}")

            thread = threading.Thread(
                target=self.handle_client, args=(client, addr))
            thread.start()
            print(
                f"[ACTIVE CONNECTIONS]: {threading.active_count() - 1} clients are connected!")
            #self.handle_client(client,addr)

    def stop_server(self):
        self.shutdown(socket.SHUT_RDWR)
        self.close()

    def broadcast_to_all(self, message):
        for client in self.clients:
            thread = threading.Thread(
                target=self.send_a_message_to_the_client, args=())
            self.send_a_message_to_the_client(client)
class ActiveClient(socket.socket):
    def __init__(self, server_address=(LOCAL_IP, LOCAL_PORT)):
        super().__init__()
        self.parity_dict = {}
        self.parity_msgs_sent = 0
        self.server_address = server_address
        #self.__setattr__("address",None)
        self.connect(self.server_address)
        self.connected = True

    def ask_for_parity_from_server(self, indexes: list):
        self.parity_msgs_sent += 1
        msg_no = self.parity_msgs_sent

        def asking(indexes):
            indexes = str(indexes)
            indexes = indexes[1:-1]
            self.send_a_message_to_server(f"ask_parity:{msg_no}:{indexes}")

        def receiving():
            while True:
                msg_recvd = self.receive_a_message_from_server()

                if msg_recvd:
                    if msg_recvd.startswith("ask_parity"):

                        splitted_msg_recvd = msg_recvd.split(":")

                        def exists_in_parity_dict(msg_no):
                            parity = self.parity_dict.get(f"{msg_no}")
                            if parity == None:
                                return False
                            else:
                                return True

                        msg_no_returned = int(splitted_msg_recvd[1])
                        parity = int(splitted_msg_recvd[2])

                        if msg_no_returned == msg_no:
                            return parity
                        elif exists_in_parity_dict(msg_no):
                            parity = self.parity_dict.get(f"{msg_no}")
                            self.parity_dict.pop(f"{msg_no}")
                            return parity
                        else:
                            self.parity_dict.add(f"{msg_no_returned}", parity)
        asking(indexes)
        parity = receiving()

        return parity



    def receive_from_server(self):
        connected = True
        while connected:
            msg_received = self.receive_a_message_from_server()
            print(f"[SERVER]: {msg_received}")

    def write_to_server(self):
        connected = True
        while connected:
            msg_to_send = input("Enter your indexes: ")
            indexes_o = msg_to_send
            indexes_o = indexes_o.split(",")
            indexes = []
            for i in indexes_o:
                indexes.append(int(i))
            if msg_to_send == "disconnect":
                connected = False
            else:
                self.ask_for_parity_from_server(indexes)
        self.close()
 