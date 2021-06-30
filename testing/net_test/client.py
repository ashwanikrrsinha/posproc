# python -m testing.net_test.client

from constants import PUBLIC_SERVER, LOCAL_SERVER
from networking.networking_class import Client

c = Client()

p = c.ask_for_parity_from_server(indexes=[1,2,3])

print(f"Parity is: {p}")