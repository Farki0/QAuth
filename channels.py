"""
QAuth - channels
================
Factory functions for quantum and classical channels.
Noise / loss models are optional parameters, so errors can be added later
without changing the network code.
"""
from netsquid.components import QuantumChannel, ClassicalChannel
from netsquid.components.models import FibreDelayModel


def make_quantum_channel(name, length=1.0, noise_model=None, loss_model=None):
    """One-directional quantum channel.

    :param name: channel name
    :param length: length in km (delay is computed from it)
    :param noise_model: optional quantum noise model (e.g. DepolarNoiseModel)
    :param loss_model: optional quantum loss model (e.g. FibreLossModel)
    """
    models = {"delay_model": FibreDelayModel()}
    if noise_model is not None:
        models["quantum_noise_model"] = noise_model
    if loss_model is not None:
        models["quantum_loss_model"] = loss_model
    return QuantumChannel(name, length=length, models=models)


def make_classical_channel(name, length=1.0, noise_model=None):
    """One-directional classical channel.

    :param name: channel name
    :param length: length in km (delay is computed from it)
    :param noise_model: optional classical noise model
    """
    models = {"delay_model": FibreDelayModel()}
    if noise_model is not None:
        models["classical_noise_model"] = noise_model
    return ClassicalChannel(name, length=length, models=models)
