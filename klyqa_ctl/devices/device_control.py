"""Device control"""

from klyqa_ctl.controller_data import ControllerData
from klyqa_ctl.devices.device import Device
from klyqa_ctl.devices.light.light import Light
from klyqa_ctl.devices.vacuum.vacuum import VacuumCleaner


def create_device(unit_id: str, product_id: str) -> Device:
    """Create a device by product id in the controller data."""

    device: Device

    if ".lighting" in product_id:
        device = Light()
    elif ".cleaning" in product_id:
        device = VacuumCleaner()
    else:
        device = Device()
    device.u_id = unit_id
    device.product_id = product_id

    return device


def get_or_create_device(
    controller_data: ControllerData, unit_id: str, product_id: str
) -> Device:
    """Get or create a device from the controller data. Read in device
    config when new device is created."""

    if unit_id in controller_data.devices:
        return controller_data.devices[unit_id]
    else:
        dev: Device = create_device(unit_id, product_id)
        if product_id in controller_data.device_configs:
            dev.read_device_config(
                device_config=controller_data.device_configs[product_id]
            )
        controller_data.devices[unit_id] = dev

        return dev
