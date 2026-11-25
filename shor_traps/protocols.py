"""
QAuth - protocols
=================
Quantum authentication with a pre-shared secret bit string (see keys.py).

AliceProtocol : Shor encode (1 -> 9 qubits) -> hide the 9 qubits among 16,
                the 7 free slots get trap qubits -> send the 16 qubits to Eve
EveProtocol   : forwards every message untouched (no attack for now)
BobProtocol   : reorder with the key -> check the traps -> decode the Shor code
                -> accept iff every trap is correct AND the syndrome is zero

Someone without the key does not know which slots hold the Shor qubits and
which hold traps (and in which basis), so a modification is likely detected.
"""
import netsquid as ns
from netsquid.protocols import NodeProtocol
from netsquid.qubits import operators as ops

from network import qport, cport
from keys import parse_key, N_TOTAL


# ==========================================================================
# Shor code [[9,1,3]]
# ==========================================================================
#   |0>_L = (|000> + |111>)(|000> + |111>)(|000> + |111>) / 2^(3/2)
#   |1>_L = (|000> - |111>)(|000> - |111>)(|000> - |111>) / 2^(3/2)
#
# Encoding circuit (q0 = data qubit, q1..q8 = |0> ancillas):
#   CNOT q0->q3, q0->q6          (phase-flip protection, 3 blocks)
#   H    q0, q3, q6
#   CNOT q0->q1, q0->q2          (bit-flip protection inside each block)
#   CNOT q3->q4, q3->q5
#   CNOT q6->q7, q6->q8
# Decoding is the same circuit in reverse order; the ancillas are measured,
# which gives the syndrome. All zeros means no error was detected.

_OUTER = [(0, 3), (0, 6)]
_HADAMARD = [0, 3, 6]
_INNER = [(0, 1), (0, 2), (3, 4), (3, 5), (6, 7), (6, 8)]


def _cnot(qubits, control, target):
    ns.qubits.operate([qubits[control], qubits[target]], ops.CNOT)


def _measure(qubit):
    return ns.qubits.measure(qubit)[0]


def shor_encode(data_qubit):
    """Encode `data_qubit` into the Shor code. Returns a list of 9 qubits
    (index 0 is the original data qubit)."""
    qubits = [data_qubit] + ns.qubits.create_qubits(8)
    for c, t in _OUTER:
        _cnot(qubits, c, t)
    for i in _HADAMARD:
        ns.qubits.operate(qubits[i], ops.H)
    for c, t in _INNER:
        _cnot(qubits, c, t)
    return qubits


def shor_decode(qubits, correct=True):
    """Decode a Shor codeword (9 qubits).

    The ancillas are measured to obtain the syndrome. If `correct` is True,
    a single X / Z error is corrected on the data qubit.

    :returns: (data_qubit, syndrome) where syndrome is a dict:
              {"bit_flip": [(s1, s2), (s1, s2), (s1, s2)],  # one per block
               "phase_flip": (s1, s2)}
    """
    # 1. Bit-flip syndrome inside each block
    bit_flip = []
    for b0 in (0, 3, 6):
        _cnot(qubits, b0, b0 + 2)
        _cnot(qubits, b0, b0 + 1)
        s = (_measure(qubits[b0 + 1]), _measure(qubits[b0 + 2]))
        bit_flip.append(s)
        if correct and s == (1, 1):          # error was on b0 itself
            ns.qubits.operate(qubits[b0], ops.X)

    # 2. Phase-flip syndrome between the blocks
    for i in _HADAMARD:
        ns.qubits.operate(qubits[i], ops.H)
    for c, t in reversed(_OUTER):
        _cnot(qubits, c, t)
    phase_flip = (_measure(qubits[3]), _measure(qubits[6]))
    if correct and phase_flip == (1, 1):     # phase error was on block 0
        ns.qubits.operate(qubits[0], ops.X)

    return qubits[0], {"bit_flip": bit_flip, "phase_flip": phase_flip}


def syndrome_is_zero(syndrome):
    """True if no error was detected."""
    return (all(s == (0, 0) for s in syndrome["bit_flip"])
            and syndrome["phase_flip"] == (0, 0))


# ==========================================================================
# Trap qubits
# ==========================================================================
def make_trap(state):
    """Create one trap qubit in |0>, |1>, |+> or |->."""
    qubit, = ns.qubits.create_qubits(1)
    if state in ("1", "-"):
        ns.qubits.operate(qubit, ops.X)
    if state in ("+", "-"):
        ns.qubits.operate(qubit, ops.H)
    return qubit


def check_trap(qubit, state):
    """Measure the trap in its own basis; True if it is still in `state`.
    Z basis: outcome 0 = |0>, 1 = |1>.  X basis: outcome 0 = |+>, 1 = |->."""
    if state in ("0", "1"):
        outcome = ns.qubits.measure(qubit, observable=ops.Z)[0]
        return outcome == int(state == "1")
    outcome = ns.qubits.measure(qubit, observable=ops.X)[0]
    return outcome == int(state == "-")


# ==========================================================================
# Protocols
# ==========================================================================
class AliceProtocol(NodeProtocol):
    """Authenticates and sends `data_qubit` to `peer` (default: Eve):
        1. encode with the Shor code                       (9 qubits)
        2. put Shor qubit i into slot shor_positions[i]    (16 slots)
        3. fill the 7 free slots with trap qubits
        4. send the 16 qubits
    """

    def __init__(self, node, data_qubit, key, peer="Eve", verbose=True):
        super().__init__(node, name=f"Alice_{node.name}")
        self.data_qubit = data_qubit
        self.key = parse_key(key)
        self.peer = peer
        self.verbose = verbose

    def run(self):
        codeword = shor_encode(self.data_qubit)
        slots = [None] * N_TOTAL
        for qubit, pos in zip(codeword, self.key["shor_positions"]):
            slots[pos] = qubit
        for pos, state in zip(self.key["trap_positions"], self.key["trap_states"]):
            slots[pos] = make_trap(state)

        self.node.ports[qport(self.peer)].tx_output(slots)
        if self.verbose:
            print(f"[{ns.sim_time():8.1f} ns] {self.node.name} sends {len(slots)} qubits "
                  f"(9 Shor + {N_TOTAL - 9} traps) -> {self.peer}")
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
    """Waits for the 16 qubits from `peer` (default: Eve):
        1. pick out the Shor qubits and the traps using the key
        2. measure every trap in its own basis, compare with the key
        3. decode the Shor code, measure the syndrome
        4. accept iff all traps are correct and the syndrome is zero

    Result (in `self.result`):
        "accepted"   -> decoded qubit is in memory position 0
        "rejected"   -> a trap or the syndrome shows a modification
        "no message" -> nothing arrived within `timeout` ns
    Details in `self.trap_errors` (number of wrong traps) and `self.syndrome`.
    """

    def __init__(self, node, key, peer="Eve", timeout=100_000, verbose=True):
        super().__init__(node, name=f"Bob_{node.name}")
        self.key = parse_key(key)
        self.peer = peer
        self.timeout = timeout
        self.verbose = verbose
        self.result = None
        self.trap_errors = None
        self.syndrome = None

    def run(self):
        port = self.node.ports[qport(self.peer)]
        expr = yield self.await_port_input(port) | self.await_timer(self.timeout)

        if expr.second_term.value:
            self.result = "no message"
            self._print(f"[{ns.sim_time():8.1f} ns] {self.node.name}: nothing arrived "
                        f"from {self.peer} -> REJECT")
            return

        slots = port.rx_input().items
        self._print(f"[{ns.sim_time():8.1f} ns] {self.node.name} received {len(slots)} qubits "
                    f"from {self.peer}, checking traps and decoding...")
        if len(slots) != N_TOTAL:
            self.result = "rejected"
            self._print(f"           expected {N_TOTAL} qubits -> REJECT")
            return

        # 1.-2. traps
        self.trap_errors = sum(
            not check_trap(slots[pos], state)
            for pos, state in zip(self.key["trap_positions"], self.key["trap_states"]))
        self._print(f"           traps: {len(self.key['trap_states']) - self.trap_errors}"
                    f"/{len(self.key['trap_states'])} correct")

        # 3. Shor code
        codeword = [slots[pos] for pos in self.key["shor_positions"]]
        data_qubit, self.syndrome = shor_decode(codeword, correct=True)
        self._print(f"           syndrome: bit-flip {self.syndrome['bit_flip']}, "
                    f"phase-flip {self.syndrome['phase_flip']}")

        # 4. decision
        if self.trap_errors == 0 and syndrome_is_zero(self.syndrome):
            self.result = "accepted"
            self.node.qmemory.put(data_qubit, positions=0)
            self._print("           -> ACCEPT, decoded qubit stored in memory")
        else:
            self.result = "rejected"
            self._print("           -> REJECT, the message was modified")

    def _print(self, text):
        if self.verbose:
            print(text)
