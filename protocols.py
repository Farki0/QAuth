"""
QAuth - protocols
=================
Non-interactive quantum authentication with a pre-shared key (k, x, y),
code family Q_k = C_k (Shor).

AliceProtocol : Shor encode -> E_y (syndrome y) -> C_k (code Q_k) -> P_x (encryption)
                -> send to Eve
EveProtocol   : forwards every message untouched (no attack for now)
BobProtocol   : P_x (decryption) -> C_k^-1 -> measure syndrome y' -> accept iff y' == y
"""
import netsquid as ns
from netsquid.protocols import NodeProtocol

from network import qport, cport
from shor import shor_encode, shor_decode, apply_syndrome
from keys import apply_code_key, undo_code_key, pauli_encrypt, pauli_decrypt


class AliceProtocol(NodeProtocol):
    """Authenticates and sends `data_qubit` to `peer` (default: Eve):
        1. encode with the Shor code            (9 qubits)
        2. apply E_y -> codeword has syndrome y   (key["y"])
        3. apply C_k -> codeword of the code Q_k  (key["k"])
        4. apply P_x -> encryption                (key["x"])
    """

    def __init__(self, node, data_qubit, key, peer="Eve", verbose=True):
        super().__init__(node, name=f"Alice_{node.name}")
        self.data_qubit = data_qubit
        self.key = key
        self.peer = peer
        self.verbose = verbose

    def run(self):
        codeword = shor_encode(self.data_qubit)
        apply_syndrome(codeword, self.key["y"])
        codeword = apply_code_key(codeword, self.key["k"])
        pauli_encrypt(codeword, self.key["x"])
        self.node.ports[qport(self.peer)].tx_output(codeword)
        if self.verbose:
            print(f"[{ns.sim_time():8.1f} ns] {self.node.name} sends authenticated codeword "
              f"({len(codeword)} qubits) -> {self.peer}")
        yield from ()


class EveProtocol(NodeProtocol):
    """Eve sits between `peer_a` and `peer_b` and receives everything,
    in both directions, on both the quantum and the classical channel.
    For now she has no attack: every message is forwarded untouched.
    """

    def __init__(self, node, peer_a="Alice", peer_b="Bob", verbose=True):
        super().__init__(node, name=f"Eve_{node.name}")
        self.peers = (peer_a, peer_b)
        self.verbose = verbose
        self.log = []          # (time, kind, src, dst)

    def run(self):
        # (input port, output port, kind, src, dst) for every route
        routes = []
        for src, dst in (self.peers, self.peers[::-1]):
            routes.append((qport(src), qport(dst), "quantum", src, dst))
            routes.append((cport(src), cport(dst), "classical", src, dst))

        while True:
            expr = None
            for in_port, *_ in routes:
                ev = self.await_port_input(self.node.ports[in_port])
                expr = ev if expr is None else expr | ev
            yield expr

            for in_port, out_port, kind, src, dst in routes:
                msg = self.node.ports[in_port].rx_input()
                if msg is not None:
                    self._forward(msg.items, kind, src, dst, out_port)

    def _forward(self, items, kind, src, dst, out_port):
        self.log.append((ns.sim_time(), kind, src, dst))
        if self.verbose:
            print(f"[{ns.sim_time():8.1f} ns] Eve forwards {kind} ({len(items)} items) "
                  f"{src} -> {dst}")
        self.node.ports[out_port].tx_output(list(items))


class BobProtocol(NodeProtocol):
    """Waits for an authenticated Shor codeword from `peer` (default: Eve):
        1. apply P_x      -> decryption             (key["x"])
        2. apply C_k^-1   -> back to the Shor code  (key["k"])
        3. decode, measure the syndrome y'
        4. accept iff y' == y                      (key["y"])

    Result (in `self.result`):
        "accepted"   -> y' == y, decoded qubit is in memory position 0
        "rejected"   -> y' != y, the message was tampered with
        "no message" -> nothing arrived within `timeout` ns
    """

    def __init__(self, node, key, peer="Eve", timeout=100_000, verbose=True):
        super().__init__(node, name=f"Bob_{node.name}")
        self.key = key
        self.verbose = verbose
        self.peer = peer
        self.timeout = timeout
        self.result = None
        self.syndrome = None

    def run(self):
        port = self.node.ports[qport(self.peer)]
        expr = yield self.await_port_input(port) | self.await_timer(self.timeout)

        if expr.second_term.value:
            self.result = "no message"
            self._print(f"[{ns.sim_time():8.1f} ns] {self.node.name}: nothing arrived "
                  f"from {self.peer} -> REJECT")
            return

        qubits = port.rx_input().items
        self._print(f"[{ns.sim_time():8.1f} ns] {self.node.name} received {len(qubits)} qubits "
              f"from {self.peer}, decrypting and decoding...")

        pauli_decrypt(qubits, self.key["x"])
        qubits = undo_code_key(qubits, self.key["k"])
        # correct=True removes E_y (one X per block + one block phase flip),
        # so the data qubit is restored if the syndrome matches.
        data_qubit, self.syndrome = shor_decode(qubits, correct=True)
        expected = self.key["y"]
        self._print(f"           measured y': bit-flip {self.syndrome['bit_flip']}, "
              f"phase-flip {self.syndrome['phase_flip']}")
        self._print(f"           expected y : bit-flip {expected['bit_flip']}, "
              f"phase-flip {expected['phase_flip']}")

        if self.syndrome == expected:
            self.result = "accepted"
            self.node.qmemory.put(data_qubit, positions=0)
            self._print(f"           -> ACCEPT, decoded qubit stored in memory")
        else:
            self.result = "rejected"
            self._print(f"           -> REJECT, the message was tampered with")

    def _print(self, text):
        if self.verbose:
            print(text)
