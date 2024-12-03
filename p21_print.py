#!/bin/python
import serial
import struct
from PIL import Image, ImageDraw
from packaging.version import Version


class BatteryData:
    def __init__(self, data):
        # The assumption is, that the printer returns the current battery
        # percentage as the hex value of the byte. 0x75 being 75% etc.
        self.battery_level = int(data[0].hex())
        self.charging = data[1]

    def __str__(self):
        class ChargingString:
            def __init__(self, charging):
                self.charging = charging

            def __str__(self):
                match self.charging:
                    case True:
                        return "Charging"
                    case False:
                        return "Not Charging"
                    case _:
                        return "Unknown"

        # The printer always returns 99% charge when plugged.
        if self.charging:
            return (
                f"Battery Level: {self.battery_level}%\n"
                f"Charging: {ChargingString(self.charging)}\n"
                f"Unplug the printer to get a current battery reading."
            )
        else:
            return (
                f"Battery Level: {self.battery_level}%\n"
                f"Charging: {ChargingString(self.charging)}"
            )


class DeviceConfig:
    def mapTimeoutValue(self, byteValue):
        match byteValue:
            case 0:
                return 0
            case 1:
                return 15
            case 2:
                return 30
            case 3:
                return 60

    def __init__(self, data):
        self.dpi_resolution = data[0]
        self.hardware_version = Version(f"{data[1]}.{data[2]}.{data[3]}")
        self.second_firmware_version = Version(f"{data[4]}.{data[5]}.{data[6]}")
        self.timeout_setting = self.mapTimeoutValue(data[7])
        self.beep_setting = data[8]

    def __str__(self):
        class TimeoutString:
            def __init__(self, timeout_setting):
                self.timeout_setting = timeout_setting

            def __str__(self):
                match self.timeout_setting:
                    case 0:
                        return "Never"
                    case 15:
                        return "15 minutes"
                    case 30:
                        return "30 minutes"
                    case 60:
                        return "60 minutes"
                    case _:
                        return "Unknown"

        class BeepString:
            def __init__(self, beep_setting):
                self.beep_setting = beep_setting

            def __str__(self):
                match self.beep_setting:
                    case True:
                        return "On"
                    case False:
                        return "Off"
                    case _:
                        return "Unknown"

        return (
            f"DPI Resolution: {self.dpi_resolution}\n"
            f"Hardware Version: {self.hardware_version}\n"
            f"Second Firmware Version: {self.second_firmware_version}\n"
            f"Timeout: {TimeoutString(self.timeout_setting)}\n"
            f"Beep: {BeepString(self.beep_setting)}"
        )


def convert_image_to_2bit(image):
    # Open the image
    
    # Convert the image to 2-bit grayscale using dithering
    image = image.convert('L')
    image = image.point(lambda p: p // 64 * 64)  # Reduce to 4 levels (0, 64, 128, 192)
    
    # Get the image data
    pixels = image.getdata()
    
    # Pack pixels into bytes (4 pixels per byte) in MSB order
    packed_data = bytearray()
    byte = 0
    bit_count = 0
    
    for pixel in pixels:
        # Convert pixel to 2-bit value
        if pixel < 64:
            value = 0
        elif pixel < 128:
            value = 1
        elif pixel < 192:
            value = 2
        else:
            value = 3
        
        # Pack the 2-bit value into the byte in MSB order
        byte |= (value << (6 - bit_count * 2))
        bit_count += 1
        
        if bit_count == 4:
            packed_data.append(byte)
            byte = 0
            bit_count = 0
    
    # Append the last byte if there are remaining bits
    if bit_count > 0:
        packed_data.append(byte)
    
    return packed_data

def get_config():
    data = get_data("CONFIG?")
    configdata = clean_serial_response(data, "CONFIG ", 10)
    unpacked_data = struct.unpack(">hBBBBBBB?", configdata)
    return DeviceConfig(unpacked_data)


def get_battery():
    response = get_data("BATTERY?")
    configdata = clean_serial_response(response, "BATTERY ", 2)
    unpacked_data = struct.unpack(">c?", configdata)
    return BatteryData(unpacked_data)


def clean_serial_response(response, prefix, expected_len):
    # Cut off the prefix and the CRLF at the end.
    cleaned_response = response[len(prefix) : -2]
    # Validate the response
    if (
        not response.startswith(prefix.encode())
        or len(cleaned_response) != expected_len
    ):
        raise ValueError(f"Invalid response: {response.hex()}")
    return cleaned_response

def get_data(command):
    try:
        with serial.Serial("/dev/rfcomm0", 115200, timeout=1) as ser:
            # Request the current configuration from the printer
            ser.write(f"{command}\r\n".encode())
            response = ser.readline()
            ser.close()
            return response
    except serial.SerialException as e:
        print(f"Failed to get config via serial connection: {e}")
        return


def send_print_data(data):
    try:
        with serial.Serial("/dev/rfcomm0", 115200, timeout=1) as ser:
            print(f"Sending {len(data)} of bytes to the printer")
            ser.write(data)
            in_bin = ser.readline()
            in_hex = in_bin.hex()
            print(in_hex)
    except serial.SerialException as e:
        print(f"Failed to send data via serial connection: {e}")
        return


def build_serial_data(imagedata):
    serial_data = """\033!o\r\n
   SIZE 14.0 mm,40.0 mm\r\n
GAP 5.0 mm,0 mm\r\n
DIRECTION 0,0\r\n
DENSITY 15\r\n
CLS\r\n
BITMAP 0,0,12,284,1,""".encode()
    serial_data += imagedata

    serial_data += """\r\n
PRINT 1\r\n""".encode()
    return serial_data

def draw_diagonal_lines(width, height):
    # Create a new image with white background
    image = Image.new('L', (width, height), 255)
    draw = ImageDraw.Draw(image)
    
    # Draw 45-degree diagonal lines
    for x in range(0, width, 4):
        draw.line((x, 0, 0, x), fill=0)
        draw.line((width - x, height, width, height - x), fill=0)
    
    for y in range(0, height, 4):
        draw.line((0, y, y, 0), fill=0)
        draw.line((width, height - y, width - y, height), fill=0)
    
    return image

def main():
    print("Printer configuration:")
    print(get_config())
    print("Printer battery:")
    print(get_battery())
    image = Image.open("nelko_test_image.bmp")
    #image = draw_diagonal_lines(48, 284)
    bitdata = convert_image_to_2bit(image)

    if len(bitdata) < 3408:
        bitdata = bitdata.ljust(3408- len(bitdata), b"\xff")

    send_print_data(build_serial_data(bitdata))


if __name__ == "__main__":
    main()
