from .sim import SimTransport
from .udp import UdpTransport

TRANSPORTS = ("sim", "udp")


def get_transport(
    node_id: str,
    *,
    kind: str = "sim",
    hub: str = "default",
    udp_listen: bool = False,
):
    if kind == "udp":
        return UdpTransport.get(node_id, listen=udp_listen)
    return SimTransport.get(node_id, hub=hub)


__all__ = ["SimTransport", "UdpTransport", "get_transport", "TRANSPORTS"]
