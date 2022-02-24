import wmi


def is_laptop() -> bool:
    # If the device has a battery, it's pretty certainly a laptop
    batteries = wmi.WMI().Win32_Battery()
    if len(batteries):
        return True

    ram_sticks = wmi.WMI().Win32_PhysicalMemory()
    for stick in ram_sticks:
        # If we have DIMM RAM, we're most likely not a laptop
        if stick.FormFactor == 8:
            return False
        # And if we have SODIMM RAM, we're most likely a laptop
        if stick.FormFactor == 12:
            return True

    if wmi.WMI().Win32_ComputerSystem()[0].PCSystemType == 2:
        return True

    return False


def get_gpu_manufacturers(wmi_inst: wmi.WMI = None) -> list:
    """
    Collects the manufacturers of all GPUs installed in the system
    :param wmi_inst: A WMI instance to use. If not specified, will construct a new one
    :return: A list of all detected manufacturers
    """
    if wmi_inst is None:
        wmi_inst = wmi.WMI()

    manufacturers = set()
    for gpu in wmi_inst.Win32_VideoController():
        manufacturers.add(gpu.AdapterCompatibility)
    return list(manufacturers)

