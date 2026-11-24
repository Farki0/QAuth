"""
QAuth - Shor code [[9,1,3]]
===========================
Encodes 1 logical qubit into 9 physical qubits:

    |0>_L = (|000> + |111>)(|000> + |111>)(|000> + |111>) / 2^(3/2)
    |1>_L = (|000> - |111>)(|000> - |111>)(|000> - |111>) / 2^(3/2)

Encoding circuit (q0 = data qubit, q1..q8 = |0> ancillas):
    CNOT q0->q3, q0->q6          (phase-flip protection, 3 blocks)
    H    q0, q3, q6
    CNOT q0->q1, q0->q2          (bit-flip protection inside each block)
    CNOT q3->q4, q3->q5
    CNOT q6->q7, q6->q8
Decoding is the same circuit in reverse order. During decoding the ancillas
are measured, which gives the syndrome:
    - bit-flip syndrome of each block (q1,q2), (q4,q5), (q7,q8)
    - phase-flip syndrome (q3,q6)
All zeros means no error was detected.
"""
import netsquid as ns
from netsquid.qubits import operators as ops

_OUTER = [(0, 3), (0, 6)]
_HADAMARD = [0, 3, 6]
_INNER = [(0, 1), (0, 2), (3, 4), (3, 5), (6, 7), (6, 8)]


def _cnot(qubits, control, target):
    ns.qubits.operate([qubits[control], qubits[target]], ops.CNOT)


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


def _measure(qubit):
    return ns.qubits.measure(qubit)[0]


def shor_decode(qubits, correct=True):
    """Decode a Shor codeword (9 qubits).

    The ancillas are measured to obtain the syndrome. If `correct` is True,
    a single X / Z error is corrected on the data qubit.

    :returns: (data_qubit, syndrome) where syndrome is a dict:
              {"bit_flip": [(s1, s2), (s1, s2), (s1, s2)],  # one per block
               "phase_flip": (s1, s2)}
    """
    # 1. Bit-flip syndrome inside each block (b0, b1, b2)
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


# Which single error gives which syndrome pair:
#   (1, 1) -> first qubit/block, (1, 0) -> second, (0, 1) -> third, (0, 0) -> none
_SYNDROME_TO_OFFSET = {(1, 1): 0, (1, 0): 1, (0, 1): 2}


def apply_syndrome(qubits, syndrome):
    """Apply the Pauli error E_y that moves a codeword into the subspace with
    the given `syndrome` (used by Alice to encode "with syndrome y")."""
    for block, pair in enumerate(syndrome["bit_flip"]):
        if pair in _SYNDROME_TO_OFFSET:
            ns.qubits.operate(qubits[3 * block + _SYNDROME_TO_OFFSET[pair]], ops.X)
    pair = syndrome["phase_flip"]
    if pair in _SYNDROME_TO_OFFSET:
        ns.qubits.operate(qubits[3 * _SYNDROME_TO_OFFSET[pair]], ops.Z)
