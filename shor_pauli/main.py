"""
QAuth - full protocol: key-dependent code + Pauli encryption
============================================================
Alice and Bob share a secret key (k, x, y) before the protocol.
Alice: Shor encode -> E_y -> C_k -> P_x -> Eve.  Eve: forwards (no attack for now).
Bob:   P_x -> C_k^-1 -> syndrome y' -> accept iff y' == y.

Expected result: accept, fidelity 1.

Check (only for testing): if Bob accepted, we compare his qubit with |psi>.
"""
import numpy as np
import netsquid as ns
from netsquid.qubits import operators as ops

from network import create_network
from protocols import AliceProtocol, EveProtocol, BobProtocol
from keys import generate_key


def make_psi(theta=1.0, phi=0.0):
    """|psi> = cos(theta/2)|0> + e^{i phi} sin(theta/2)|1>, returns (qubit, reference ket).

    theta: polar angle on the Bloch sphere (Ry rotation)
    phi:   relative phase (Rz rotation; the global phase it adds does not affect fidelity)
    """
    qubit, = ns.qubits.create_qubits(1)
    ns.qubits.operate(qubit, ops.create_rotation_op(theta, (0, 1, 0)))
    ns.qubits.operate(qubit, ops.create_rotation_op(phi, (0, 0, 1)))
    ket = np.array([np.cos(theta / 2), np.exp(1j * phi) * np.sin(theta / 2)])
    return qubit, ket


def run(seed=None, verbose=True):
    ns.sim_reset()
    network = create_network(qmemory_positions=9)
    alice, eve, bob = (network.get_node(n) for n in ("Alice", "Eve", "Bob"))

    key = generate_key(seed=seed)    # pre-shared, NOT sent over the network
    if verbose:
        print(f"Shared key: k = {key['k']}")
        print(f"            x = {key['x']}")
        print(f"            y = {key['y']}")

    psi, psi_ket = make_psi()

    bob_protocol = BobProtocol(bob, key, verbose=verbose)
    protocols = [
        AliceProtocol(alice, psi, key, verbose=verbose),
        EveProtocol(eve, verbose=verbose),
        bob_protocol,
    ]
    for p in protocols:
        p.start()
    ns.sim_run()

    fidelity = None
    if bob_protocol.result == "accepted":
        qubit = bob.qmemory.peek(0)[0]
        fidelity = ns.qubits.fidelity(qubit, psi_ket)
    if verbose:
        print(f"Bob's result: {bob_protocol.result}")
        if fidelity is not None:
            print(f"Fidelity with |psi>: {fidelity:.4f}")
        print()
    return bob_protocol.result, fidelity


if __name__ == "__main__":
    print("=== Eve forwards ===")
    run()
