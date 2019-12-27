"""This is Server that mimics Vendekin Hardware,
 all you have to do is on the terminal type this
 as "python uart_peripheral.py <machine name> <vend or no_vend>
 When the App connects to the Server it starts notification and the
 server responds back this all is done in the Start Notify function,
 once this is done the app writes messages to the Server and the Write
 Value function is called and it processes the Bytes and returns a
 response accordingly.
 To Add a New Machine just Add the Machine Name in the Machine_map and
 its response messages accordingly and your are done and you can mimic
 a new machine
 """
import dbus
import dbus.mainloop.glib
import sys
import re
import time
import logging
from example_advertisement import Advertisement
from example_advertisement import register_ad_cb, register_ad_error_cb
from example_gatt_server import Service, Characteristic
from example_gatt_server import register_app_cb, register_app_error_cb
from gi.repository import GObject

BLUEZ_SERVICE_NAME = 'org.bluez'
DBUS_OM_IFACE = 'org.freedesktop.DBus.ObjectManager'
LE_ADVERTISING_MANAGER_IFACE = 'org.bluez.LEAdvertisingManager1'
GATT_MANAGER_IFACE = 'org.bluez.GattManager1'
GATT_CHRC_IFACE = 'org.bluez.GattCharacteristic1'
UART_SERVICE_UUID = '49535343-fe7d-4ae5-8fa9-9fafd205e455'
UART_RX_CHARACTERISTIC_UUID = '6e400002-b5a3-f393-e0a9-e50e24dcca9e'
UART_TX_CHARACTERISTIC_UUID = '6e400003-b5a3-f393-e0a9-e50e24dcca9e'
VENDEKIN_UUID = '49535343-1e4d-4bd9-ba61-23c647249616'
LOCAL_NAME = "Vendekin Hardware Simulator"
mainloop = None
arguments_list = sys.argv
machine_name = sys.argv[1]
vend_status = sys.argv[2]
logging.root.setLevel(logging.NOTSET)
cash_string = {
    'Alpha-Numeric': 'A01-1023@A02-1011@B01-1013@B02-1007',
    'Numeric': '101-100@102-100@201-100@202-100',
}

success_codes = {
    'success_seaga': 'start ssn\r\nvend req\r\nvnd sec\r\nsucess\r\n019091001\r\n019091001\r\n019091001\r\n019091001\r\n019091001\r\nread enable\r\n',
    'success_dexi-narco': 'start ssn\r\nvend req\r\nvnd sec\r\nsucess\r\n019091001\r\nssn complete\r\nend ssn\r\n',
    'success_marico': 'COMMAND SUCCESS\r\ndespensing complete\r\nDispensed\r\n019091001\r\nDispensed\r\n019091001\r\nDispensed\r\n019091001\r\nDispensed\r\n019091001\r\nDispensed\r\n019091001\r\nDispensed\r\n019091001\r\nDispensed\r\n019091001\r\n'
}

error_codes = {
    'error_seaga': 'start ssn\r\nstart ssn\r\nstart ssn\r\nstart ssn\r\nstart ssn\r\nstart ssn\r\nstart ssn\r\nno vend case\r\nread enable\r\n',
    'error_dexi-narco': 'start ssn\r\nno vend case\r\n019091001\r\nssn complete\r\nend ssn\r\n'
}


def ProcessCS():
    send_cash_string = cash_string.get('Alpha-Numeric')
    value = []
    for c in send_cash_string:
        value.append(dbus.Byte(c.encode()))
    return value


def ProcessD():
    send_dex_data = cash_string.get('Alpha-Numeric')
    value = []
    for c in send_dex_data:
        value.append(dbus.Byte(c.encode()))
    return value


def ACKResponse():
    response = []
    data = '\r\n'
    for v in data:
        response.append(dbus.Byte(v.encode()))
    return response


seaga = {
    '$D$': ProcessD,
    '$CS$': ProcessCS,
    '$ACK_ST$': ACKResponse
}

dexi_narco = {
    '$D$': ProcessD,
    '$CS$': ProcessCS,
    '$ACT_ST': ACKResponse
}

marico = {
    'ACK_RD': ACKResponse,
    '$CS$': ProcessCS

}

machine_map = {
    'seaga': seaga,
    'dexi-narco': dexi_narco,
    'marico': marico
}

notification_map = {
    'seaga': '\r\n',
    'dexi-narco': '\r\n',
    'marico': 'MACHINE READY\r\n',
}


def ProcessDispense(some_value):
    """
    This function picks up the success or error code
    as passed through the command line and returns a response
    accordingly

    """
    print('This is Some Value ' + some_value)
    if vend_status == 'vend':
        print('I am here')
        print('success_' + machine_name)
        value = success_codes.get('success_' + machine_name)
        print(value)
        response_string = []
        for v in value:
            response_string.append(dbus.Byte(v.encode()))
        return response_string
    elif vend_status == 'no_vend':
        value = error_codes.get('error_' + machine_name)
        response_string = []
        for v in value:
            response_string.append(dbus.Byte(v.encode()))
        return response_string
    else:
        logging.warning('Unexpected Vend Request')


class VendekinCharacteristic(Characteristic):
    def __init__(self, bus, index, service):
        Characteristic.__init__(self, bus, index, VENDEKIN_UUID,
                                ['read', 'notify', 'write'], service)

        self.received_bytes = ''
        self.notifying = False

    @staticmethod
    def ByteChecker(bytesToProcess):
        if machine_name in machine_map.keys():
            new_map = machine_map.get(machine_name)
            data_from_function = new_map[bytesToProcess]()
            return data_from_function
        else:
            logging.warning('Unexpected Machine Name')
            return None

    def WriteValue(self, value, options):
        self.received_bytes = format(bytearray(value).decode())
        self.WriteToApp(self.received_bytes)
        logging.info('This is Received: ' + self.received_bytes)

    def WriteToApp(self, giveMeBytes):
        if not self.notifying:
            return
        if len(giveMeBytes) == 31:
            respond_dispense = ProcessDispense(giveMeBytes)
            logging.info('Written to App')
            self.PropertiesChanged(GATT_CHRC_IFACE, {'Value': respond_dispense}, [])
        else:
            processed_value = self.ByteChecker(giveMeBytes)
            logging.info('Written to App')
            self.PropertiesChanged(GATT_CHRC_IFACE, {'Value': processed_value}, [])

    def StartNotify(self):
        if self.notifying:
            return
        self.notifying = True
        logging.info('Notification Started')
        notification = []
        if machine_name in notification_map.keys():
            notification_value = notification_map.get(machine_name)
            for ntfv in notification_value:
                notification.append(dbus.Byte(ntfv.encode()))
            self.PropertiesChanged(GATT_CHRC_IFACE, {'Value': notification}, [])
        else:
            logging.warning('Unexpected Machine Name')

    def StopNotify(self):
        if not self.notifying:
            return
        logging.info('Notification Stopped')
        self.notifying = False


class UartService(Service):
    def __init__(self, bus, index):
        Service.__init__(self, bus, index, UART_SERVICE_UUID, True)
        self.add_characteristic(VendekinCharacteristic(bus, 2, self))


class Application(dbus.service.Object):
    def __init__(self, bus):
        self.path = '/'
        self.services = []
        dbus.service.Object.__init__(self, bus, self.path)

    def get_path(self):
        return dbus.ObjectPath(self.path)

    def add_service(self, service):
        self.services.append(service)

    @dbus.service.method(DBUS_OM_IFACE, out_signature='a{oa{sa{sv}}}')
    def GetManagedObjects(self):
        response = {}
        for service in self.services:
            response[service.get_path()] = service.get_properties()
            chrcs = service.get_characteristics()
            for chrc in chrcs:
                response[chrc.get_path()] = chrc.get_properties()
        return response


class UartApplication(Application):
    def __init__(self, bus):
        Application.__init__(self, bus)
        self.add_service(UartService(bus, 0))


class UartAdvertisement(Advertisement):
    def __init__(self, bus, index):
        Advertisement.__init__(self, bus, index, 'peripheral')
        self.add_service_uuid(UART_SERVICE_UUID)
        self.add_local_name(LOCAL_NAME)
        self.include_tx_power = True


def find_adapter(bus):
    remote_om = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, '/'),
                               DBUS_OM_IFACE)
    objects = remote_om.GetManagedObjects()
    for o, props in objects.items():
        for iface in (LE_ADVERTISING_MANAGER_IFACE, GATT_MANAGER_IFACE):
            if iface not in props:
                continue
        return o
    return None


def vendekinGattServer():
    global mainloop
    dbus.mainloop.glib.DBusGMainLoop(set_as_default=True)
    bus = dbus.SystemBus()
    adapter = find_adapter(bus)
    if not adapter:
        print('BLE adapter not found')
        return

    service_manager = dbus.Interface(
        bus.get_object(BLUEZ_SERVICE_NAME, adapter),
        GATT_MANAGER_IFACE)
    ad_manager = dbus.Interface(bus.get_object(BLUEZ_SERVICE_NAME, adapter),
                                LE_ADVERTISING_MANAGER_IFACE)

    app = UartApplication(bus)
    adv = UartAdvertisement(bus, 0)

    mainloop = GObject.MainLoop()

    service_manager.RegisterApplication(app.get_path(), {},
                                        reply_handler=register_app_cb,
                                        error_handler=register_app_error_cb)
    ad_manager.RegisterAdvertisement(adv.get_path(), {},
                                     reply_handler=register_ad_cb,
                                     error_handler=register_ad_error_cb)
    try:
        mainloop.run()
    except KeyboardInterrupt:
        adv.Release()


vendekinGattServer()
