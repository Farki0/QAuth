"""
QAuth - network
===============
Topology:   Alice <-> Eve <-> Bob

Every link is a two-way QUANTUM and a two-way CLASSICAL channel.
There is no direct Alice-Bob link: everything goes through Eve.

Port names on a node (named after the peer):
    Alice: q_Eve, c_Eve
    Eve:   q_Alice, c_Alice, q_Bob, c_Bob
    Bob:   q_Eve, c_Eve
"""
from netsquid.nodes import Network, Node
from netsquid.components.qprocessor import QuantumProcessor

from channels import make_quantum_channel, make_classical_channel


def qport(peer):
    """Name of the quantum port towards `peer`."""
    return f"q_{peer}"


def cport(peer):
    """Name of the classical port towards `peer`."""
    return f"c_{peer}"


def make_node(name, qmemory_positions=4):
    """Node with its own quantum memory."""
    qmem = QuantumProcessor(f"{name}_QMem",
                            num_positions=qmemory_positions,
                            fallback_to_nonphysical=True)
    return Node(name, qmemory=qmem)


def create_network(node_names=("Alice", "Eve", "Bob"),
                   links=(("Alice", "Eve"), ("Eve", "Bob")),
                   length=1.0,
                   quantum_noise_model=None,
                   quantum_loss_model=None,
                   classical_noise_model=None,
                   qmemory_positions=4,
                   name="QAuthNetwork"):
    """Build the network.

    :param node_names: names of the nodes
    :param links: pairs of node names to connect (default: Alice-Eve, Eve-Bob)
    :param length: length of every channel in km
    :param quantum_noise_model: optional noise model for the quantum channels
    :param quantum_loss_model: optional loss model for the quantum channels
    :param classical_noise_model: optional noise model for the classical channels
    :param qmemory_positions: number of qubits each node can store
    """
    network = Network(name)
    network.add_nodes([make_node(n, qmemory_positions) for n in node_names])

    for name_a, name_b in links:
        a, b = network.get_node(name_a), network.get_node(name_b)
        # Quantum connection (two one-directional channels)
        network.add_connection(
            a, b,
            channel_to=make_quantum_channel(f"Q_{a.name}->{b.name}", length,
                                            quantum_noise_model, quantum_loss_model),
            channel_from=make_quantum_channel(f"Q_{b.name}->{a.name}", length,
                                              quantum_noise_model, quantum_loss_model),
            port_name_node1=qport(b.name),
            port_name_node2=qport(a.name),
            label=f"quantum_{a.name}_{b.name}",
        )
        # Classical connection (two one-directional channels)
        network.add_connection(
            a, b,
            channel_to=make_classical_channel(f"C_{a.name}->{b.name}", length,
                                              classical_noise_model),
            channel_from=make_classical_channel(f"C_{b.name}->{a.name}", length,
                                                classical_noise_model),
            port_name_node1=cport(b.name),
            port_name_node2=cport(a.name),
            label=f"classical_{a.name}_{b.name}",
        )
    return network
