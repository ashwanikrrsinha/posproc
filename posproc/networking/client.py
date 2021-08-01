import os
import pickle
# FIXME: deprecate use of pickle, use jsonpickle instead!
import secrets
from posproc.key import Key
from posproc import constants
from typing import Any, List
from posproc.networking.uebn import AdvancedClient, rename
from ellipticcurve.privateKey import PrivateKey
from ellipticcurve.publicKey import PublicKey
from posproc.networking.user_data import User
from posproc.error_correction.cascade.block import Block
from posproc.authentication import Authentication
from posproc.privacy_amplification.universal_hashing import MODEL_1

class Client(AdvancedClient):
    def __init__(self, username: str, current_key: Key = None, auth_keys: tuple[PublicKey, PrivateKey] = None,
                 server_address = (constants.LOCAL_IP, constants.LOCAL_PORT)):
        super().__init__(server_address)
        
        self.username = username
        
        auth_keys = self.check_if_auth_keys_exist()
        self._add_authentication_token(auth_Keys=auth_keys)
        if not auth_keys:
            self.save_auth_keys_as_file()
        
        self._current_key = current_key

        self.user = User(username, address=None,
                         auth_id = self.auth_id)
        
        self.authenticating = True

        self.reconciliation_status = {'cascade': 'Not yet started',
                                      'winnow': 'Not yet started',
                                      'ldpc': 'Not yet started',
                                      'polar': 'Not yet started'}
        
        
        
        self.askParitiesReplyCurrentIndex = 0
        self.qberEstimationCurrentIndex = 0  
        
    def _get_auth_keys(self):
        """
        Public Key, Private Key
        """
        return self.auth_id, self._auth_key
    
    def Initialize_Events(self):
        # @self.event
        # def onConnectionLost(Content):
        #     print('Disconnected from the server! \n')
        pass
    
    def _add_authentication_token(self, auth_Keys):
        self._auth = Authentication(auth_Keys=auth_Keys)
        self.auth_id, self._auth_key = self._auth._get_key_pair()

    def check_if_auth_keys_exist(self) -> tuple[PublicKey, PrivateKey]:
        dirpath = constants.DATA_STORAGE + self.username + '_auth_keys/'
        if os.path.exists(dirpath):
            with open(dirpath + 'privKey.pickle', 'rb') as privKeyFH:
                privKey = pickle.load(privKeyFH)

            with open(dirpath + 'pubKey.pickle', 'rb') as pubKeyFH:
                pubKey = pickle.load(pubKeyFH)
            
            # privKey = PrivateKey.fromString(b"a") #TODO: For checking authentication failure. 
            
            return (pubKey, privKey)
        else:
            return None

    def save_current_key_as_text(self, path = None):
        if not path:
            path = os.path.join(constants.DATA_STORAGE, f'{self.username}_Key.txt')
        with open(path, 'w') as fh:
            fh.write(self._current_key.__str__())

    def save_auth_keys_as_file(self):
        """
        Saves the randomly generated auth keys for future reference.
        These will only be used for a short amount of time!
        """
        pubKey, privKey = self._get_auth_keys() # (PubKey, PrivKey)
        
        dirpath = constants.DATA_STORAGE + self.username + '_auth_keys/'
        if os.path.exists(dirpath) == False:
            os.makedirs(dirpath)
        with open(dirpath + 'privKey.pickle' , 'wb') as privKeyFH:
            pickle.dump(privKey, privKeyFH)
        
        with open(dirpath + 'pubKey.pickle', 'wb') as pubKeyFH:
            pickle.dump(pubKey, pubKeyFH)

    def get_bits_for_qber(self, indexes):
        # bits_for_qber = {}
        # for index in indexes:
        #     bits_for_qber[index] = self._current_key._bits[index]
        # self._current_key.discard_bits(indexes)
        # return bits_for_qber
        bits = self._current_key.get_bits_for_qber_estimation(indexes)
        # print("Updated Noisy Key",self._current_key._bits)
        return bits
    
    def start_ursina_client(self):
        super().start_ursina_client()
        self.ursinaClient.lock.acquire()
        # ready up the authentication protocol just after client starts! 
        @self.event
        def authentication(Content):
            if Content == 'Initialize':
                msg = secrets.token_hex()
                msg_sign = self._auth.sign(msg)
                msg_to_send_dict = {'User': self.user, 'Message' : msg, 'Signature' : msg_sign}
                self.ursinaClient.send_message('authenticateClient', msg_to_send_dict)
            else:
                print('[Server]: ',Content)
                if 'Unsuccessful' in Content:
                    self.stopClient()
        self.ursinaClient.lock.release()

    def ask_parities(self, blocks: List[Block]):
        """
        Sends blocks as bytes to the server and then the server
        replies with the appropriate parities of the blocks asked.

        Args:
            blocks (list(Block)): Contains all the blocks whose parity is to be asked.

        Returns:
            parities (list(int)): Contains parities in the same order as the blocks in blocks.
        """
        self.askParitiesReplyCurrentIndex += 1
        
        # Only send the indexes for parity.
        # TODO: make this algo faster it's currently very slow for large blocks.
        block_indexes_list = [block.get_key_indexes() for block in blocks]
        # TODO: add tracking of parity messages.
        
        # print(f"Block Indexes List Bytes Sent: {len(block_indexes_list_bytes)}")

        # dict_to_send = {'askParitiesIndex':self.askParitiesReplyCurrentIndex, 'blocks_indexes':block_indexes_list}
        tuple_to_send = self.askParitiesReplyCurrentIndex, block_indexes_list
        
        # asking:
        self.send_message_to_server('askParities', tuple_to_send)
        
        # receiving:        
        name = 'askParitiesReply' + str(self.askParitiesReplyCurrentIndex)
         
        # @rename(name)
        @self.receiver_event
        def askParitiesReply():
            pass
        
        # parities = eval(name + '()')
        parities = askParitiesReply()
        
        return parities
    
    def start_reconciliation(self, reconciliation_algorithm: str):
        """
        Informs the Server(Alice) that reconciliation has started.

        Args:
            reconciliation_algorithm (str): Specify which algorithm is being used eg. 'cascade' for cascade algo.
        """
        #TODO: Maybe add authentication here!
        self.reconciliation_status[reconciliation_algorithm] = 'Active'
        self.send_message_to_server('updateReconciliationStatus', (reconciliation_algorithm,'Active'))

    def end_reconciliation(self, reconciliation_algorithm: str):
        """
        Informs the Server(Alice) that reconciliation has ended.

        Args:
            reconciliation_algorithm (str): Specify which algorithm is being used eg. 'cascade' for cascade algo.
        """
        self.reconciliation_status[reconciliation_algorithm] = 'Completed'
        self.send_message_to_server(
            'updateReconciliationStatus', (reconciliation_algorithm, 'Completed'))
    
    def get_bits_for_qber(self, indexes):
        bits = self._current_key.get_bits_for_qber_estimation(indexes)
        # print("Updated Noisy Key",self._current_key._bits)
        return bits
    
    def ask_server_for_bits_to_estimate_qber(self, indexes: list) -> dict:
        #TODO: add message no. for this also.
        self.qberEstimationCurrentIndex += 1 
        
        # print("Message Send for QBER: ", msg_to_send)

        # asking:
        self.send_message_to_server('qberEstimation' + str(self.qberEstimationCurrentIndex),(self.qberEstimationCurrentIndex, indexes))
        
        # receiving:
        name = 'qberEstimationReply' + str(self.qberEstimationCurrentIndex)
        
        @self.receiver_event
        def qberEstimationReply1():
            pass
        
        @self.receiver_event
        def qberEstimationReply2():
            pass
        
        @self.receiver_event
        def qberEstimationReply3():
            pass
        
        @self.receiver_event
        def qberEstimationReply4():
            pass      
        
                
        bits_dict = eval(name + '()')
        
        return bits_dict
    
    def ask_server_to_do_privacy_amplification(self, final_key_bytes_size = 64):
        algo_name, self._current_key = MODEL_1(self._current_key, final_key_bytes_size) 
        
        # asking:
        self.send_message_to_server('privacyAmplification', (algo_name, final_key_bytes_size))
