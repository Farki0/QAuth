"""
QAuth - shared secret key
=========================
Alice and Bob share a secret bit string BEFORE the protocol. Nothing about the
key is sent over the network.

Layout of the key (50 bits):
    bits  0..35 : 9 x 4 bits, position of Shor qubit 1, 2, ..., 9 among the
                  16 sent qubits (0000 -> slot 1, 0011 -> slot 4, ..., 1111 -> slot 16)
    bits 36..49 : 7 x 2 bits, state of the 7 trap qubits, which fill the free
                  slots in increasing order:
                      00 -> |0>,  01 -> |1>,  10 -> |->,  11 -> |+>

The 9 positions must be distinct; `generate_key` guarantees this and
`parse_key` rejects a key that does not satisfy it.
"""
import random

N_SHOR = 9                      # physical qubits of the Shor code
N_TOTAL = 16                    # qubits that are actually sent
N_TRAPS = N_TOTAL - N_SHOR      # 7
POS_BITS = 4                    # 2**4 = 16 slots
TRAP_BITS = 2
KEY_LENGTH = N_SHOR * POS_BITS + N_TRAPS * TRAP_BITS   # 36 + 14 = 50

TRAP_STATES = {"00": "0", "01": "1", "10": "-", "11": "+"}


def generate_key(seed=None):
    """Random valid key as a string of '0'/'1' characters (length 50)."""
    rng = random.Random(seed)
    positions = rng.sample(range(N_TOTAL), N_SHOR)          # 9 distinct slots
    pos_bits = "".join(format(p, f"0{POS_BITS}b") for p in positions)
    trap_bits = "".join(rng.choice("01") for _ in range(N_TRAPS * TRAP_BITS))
    return pos_bits + trap_bits


def parse_key(key):
    """Split the key into its meaning.

    :returns: dict with
        "shor_positions": slot (0..15) of Shor qubit 0..8
        "trap_positions": the 7 free slots, in increasing order
        "trap_states":    state of each trap ("0", "1", "-", "+")
    """
    if len(key) != KEY_LENGTH or set(key) - {"0", "1"}:
        raise ValueError(f"key must be {KEY_LENGTH} bits of '0'/'1'")

    shor_positions = [int(key[i:i + POS_BITS], 2)
                      for i in range(0, N_SHOR * POS_BITS, POS_BITS)]
    if len(set(shor_positions)) != N_SHOR:
        raise ValueError(f"Shor positions are not distinct: {shor_positions}")

    trap_positions = [s for s in range(N_TOTAL) if s not in shor_positions]
    offset = N_SHOR * POS_BITS
    trap_states = [TRAP_STATES[key[offset + i:offset + i + TRAP_BITS]]
                   for i in range(0, N_TRAPS * TRAP_BITS, TRAP_BITS)]
    return {"shor_positions": shor_positions,
            "trap_positions": trap_positions,
            "trap_states": trap_states}
