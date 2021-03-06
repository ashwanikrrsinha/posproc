from ellipticcurve.ecdsa import Ecdsa
from ellipticcurve.privateKey import PrivateKey


# Generate new Keys
privateKey = PrivateKey()
publicKey = privateKey.publicKey()

print(f"Public Key: {publicKey.toPem()}")
print(f"Private Key: {privateKey.toPem()}")

message = "My test message"

# Generate Signature
signature = Ecdsa.sign(message, privateKey)

# To verify if the signature is valid
print(Ecdsa.verify(message, signature, publicKey))

