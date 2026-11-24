"""
QAuth - security analysis of the code family Q_k = C_k (Shor)
=============================================================
Thanks to the encryption, any attack by Eve acts like a Pauli error E.
Bob accepts a wrong message iff C_k^-1 E C_k is a non-trivial LOGICAL operator
of the Shor code (commutes with all stabilizers, but is not a stabilizer).

C_k = random permutation + random single-qubit Clifford on every qubit, so
C_k^-1 E C_k is a uniformly random Pauli with the same weight w as E.
Therefore Eve's success probability only depends on w:

    P_success(w) = (# logical operators of weight w) / (C(9, w) * 3^w)

Paulis are stored as two 9-bit integers (x bits, z bits): X = (1,0), Z = (0,1), Y = (1,1).
"""
from math import comb

N = 9


def pauli(x_qubits=(), z_qubits=()):
    x = sum(1 << i for i in x_qubits)
    z = sum(1 << i for i in z_qubits)
    return x, z


# Stabilizer generators of the Shor code (same qubit order as shor.py)
GENERATORS = [
    pauli(z_qubits=(0, 1)), pauli(z_qubits=(1, 2)),
    pauli(z_qubits=(3, 4)), pauli(z_qubits=(4, 5)),
    pauli(z_qubits=(6, 7)), pauli(z_qubits=(7, 8)),
    pauli(x_qubits=(0, 1, 2, 3, 4, 5)),
    pauli(x_qubits=(3, 4, 5, 6, 7, 8)),
]


def commutes(p, q):
    """Two Paulis commute iff the symplectic product is even."""
    return bin((p[0] & q[1]) ^ (p[1] & q[0])).count("1") % 2 == 0


def weight(p):
    return bin(p[0] | p[1]).count("1")


def stabilizer_group():
    group = {(0, 0)}
    for g in GENERATORS:
        group |= {(s[0] ^ g[0], s[1] ^ g[1]) for s in group}
    return group


def eve_success_by_weight():
    stabilizers = stabilizer_group()
    logical_count = [0] * (N + 1)
    for x in range(1 << N):
        for z in range(1 << N):
            p = (x, z)
            if p not in stabilizers and all(commutes(p, g) for g in GENERATORS):
                logical_count[weight(p)] += 1
    return {w: logical_count[w] / (comb(N, w) * 3 ** w) for w in range(1, N + 1)}


def main():
    probs = eve_success_by_weight()
    print("Eve's success probability, Pauli attack of weight w")
    print("  w   fixed Shor code (best case for Eve)   Q_k = C_k(Shor)")
    for w, p in probs.items():
        fixed = "1 (if she picks a logical op.)" if p > 0 else "0"
        print(f"  {w}   {fixed:36s}  {p:.4f}")
    best_w = max(probs, key=probs.get)
    print(f"\nEve's best attack: weight {best_w}, success probability {probs[best_w]:.4f}")


if __name__ == "__main__":
    main()
