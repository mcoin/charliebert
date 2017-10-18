import smbus
import time

DEVICE = 0x20

address_map = {
    0x00: 'IODIRA',   0x01: 'IODIRB',   0x02: 'IPOLA',   0x03: 'IPOLB',
    0x04: 'GPINTENA', 0x05: 'GPINTENB', 0x06: 'DEFVALA', 0x07: 'DEVFALB',
    0x08: 'INTCONA',  0x09: 'INTCONB',  0x0a: 'IOCON',   0x0b: 'IOCON',
    0x0c: 'GPPUA',    0x0d: 'GPPUB',    0x0e: 'INTFA',   0x0f: 'INTFB',
    0x10: 'INTCAPA',  0x11: 'INTCAPB',  0x12: 'GPIOA',   0x13: 'GPIOB',
    0x14: 'OLATA',    0x15: 'OLATB'
}
register_map = {value: key for key, value in address_map.iteritems()}
max_len = max(len(key) for key in register_map)

def print_values(bus):
    print "-" * 20
    for addr in address_map:
        value = bus.read_byte_data(DEVICE, addr)
        print "%-*s = 0x%02X" % (max_len, address_map[addr], value)

bus = smbus.SMBus(1)
#bus.write_byte_data(DEVICE, register_map['GPPUA'], 0xFF)
#bus.write_byte_data(DEVICE, register_map['GPPUB'], 0xFF)
bus.write_byte_data(DEVICE, register_map['GPIOA'], 0xFF)
bus.write_byte_data(DEVICE, register_map['GPIOB'], 0xFF)

counter = 0
try:
    while True:
        print_values(bus)
        counter += 1
        print "counter = %s" % counter
        time.sleep(1.0)
except KeyboardInterrupt:
    print "Keyboard interrupt"
