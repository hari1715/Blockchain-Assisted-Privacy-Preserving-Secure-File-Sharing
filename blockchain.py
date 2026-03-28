import time
import json
import os

class Blockchain:
    def __init__(self):
        self.chain = []
        self.current_transactions = []
        self.chain_file = "blockchain.json"
        
        self.load_chain()
        
        if not self.chain:
            # Create the genesis block
            self.new_block(previous_hash='1', proof=100)

    def load_chain(self):
        if os.path.exists(self.chain_file):
            try:
                with open(self.chain_file, "r") as f:
                    self.chain = json.load(f)
            except Exception as e:
                print(f"Error loading blockchain: {e}")
                self.chain = []

    def save_chain(self):
        try:
            with open(self.chain_file, "w") as f:
                json.dump(self.chain, f, indent=4)
        except Exception as e:
            print(f"Error saving blockchain: {e}")

    def new_transaction(self, sender, recipient, amount):
    # self = 1, sender = 2, recipient = 3, amount = 4
        self.current_transactions.append({
        'sender': sender,
        'recipient': recipient,
        'amount': amount,
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    })
        return self.last_block['index'] + 1

    # Ensure you also have the new_block method
    def new_block(self, proof, previous_hash=None):
        import hashlib
        import json
        
        block = {
            'index': len(self.chain) + 1,
            'timestamp': time.time(),
            'transactions': self.current_transactions,
            'proof': proof,
            'previous_hash': previous_hash or self.hash(self.chain[-1]),
        }
        self.current_transactions = []
        self.chain.append(block)
        self.save_chain()
        return block

    @staticmethod
    def hash(block):
        import hashlib
        import json
        block_string = json.dumps(block, sort_keys=True).encode()
        return hashlib.sha256(block_string).hexdigest()

    @property
    def last_block(self):
        return self.chain[-1]