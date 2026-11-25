"""
QAuth - shared secret key, key-dependent code and Pauli encryption
==================================================================
The key is shared by Alice and Bob BEFORE the protocol (nothing classical is
sent during the protocol, so no authenticated classical channel is needed).

Key (for the Shor code, n = 9 qubits):
    k : chooses the code  Q_k = C_k (Shor)
        k["perm"]  : permutation of the 9 qubits          (~18.5 bits)
        k["cliff"] : one of 6 single-qubit Cliffords per qubit (~23.3 bits)
    x : 9 pairs (a, b)  -> Pauli X^a Z^b on qubit i   (quantum one-time pad, 18 bits)
    y : random Shor syndrome                         (8 bits)
        {"bit_flip": [(s1, s2)] * 3, "phase_flip": (s1, s2)}

Why k? Eve does not know C_k, so she does not know which Pauli operators are
the logical operators of Q_k -> she cannot change the message unnoticed
(only with a small probability, see analysis.py).
"""
import random

import netsquid as ns
from netsquid.qubits import operators as ops

N_QUBITS = 9

# The 6 single-qubit Cliffords (up to Paulis). Each one permutes X, Y, Z
# differently. Gates are applied left to right.
CLIFFORDS = [
    [],                     # I     : X->X, Y->Y, Z->Z
    [ops.H],                # H     : X<->Z
    [ops.S],                # S     : X<->Y
    [ops.H, ops.S],         # S.H   : X->Z->Y->X
    [ops.S, ops.H],         # H.S   : X->Y->Z->X
    [ops.H, ops.S, ops.H],  # H.S.H : Y<->Z
]


# --------------------------------------------------------------------------
# Key generation
# --------------------------------------------------------------------------
def generate_key(n_qubits=N_QUBITS, seed=None):
    rng = random.Random(seed)
    bit = lambda: rng.randint(0, 1)
    return {
        "k": {"perm": rng.sample(range(n_qubits), n_qubits),
              "cliff": [rng.randrange(len(CLIFFORDS)) for _ in range(n_qubits)]},
        "x": [(bit(), bit()) for _ in range(n_qubits)],
        "y": {"bit_flip": [(bit(), bit()) for _ in range(3)],
              "phase_flip": (bit(), bit())},
    }


# --------------------------------------------------------------------------
# Key-dependent code: Shor -> Q_k
# --------------------------------------------------------------------------
def apply_code_key(qubits, k):
    """Apply C_k: a Clifford on every qubit, then permute the qubits.
    Returns the new list of qubits (out[i] = qubits[perm[i]])."""
    for qubit, c in zip(qubits, k["cliff"]):
        for gate in CLIFFORDS[c]:
            ns.qubits.operate(qubit, gate)
    return [qubits[p] for p in k["perm"]]


def undo_code_key(qubits, k):
    """Apply C_k^-1: undo the permutation, then the inverse Cliffords."""
    original = [None] * len(qubits)
    for i, p in enumerate(k["perm"]):
        original[p] = qubits[i]
    for qubit, c in zip(original, k["cliff"]):
        for gate in reversed(CLIFFORDS[c]):
            ns.qubits.operate(qubit, gate.inv)
    return original


# --------------------------------------------------------------------------
# Pauli encryption (quantum one-time pad)
# --------------------------------------------------------------------------
def pauli_encrypt(qubits, x):
    """Apply X^a Z^b to every qubit."""
    for qubit, (a, b) in zip(qubits, x):
        if a:
            ns.qubits.operate(qubit, ops.X)
        if b:
            ns.qubits.operate(qubit, ops.Z)


def pauli_decrypt(qubits, x):
    """Undo the encryption (Paulis are self-inverse up to a global phase)."""
    for qubit, (a, b) in zip(qubits, x):
        if b:
            ns.qubits.operate(qubit, ops.Z)
        if a:
            ns.qubits.operate(qubit, ops.X)
