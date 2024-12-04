import serial
import struct
import argparse
from PIL import Image, ImageEnhance, ImageOps
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

def load_image(image):
    # Load the image
    image = Image.open(image)
    image = ImageOps.grayscale(image)
    image = ImageOps.autocontrast(image)
    enhancer = ImageEnhance.Contrast(image)
    image = enhancer.enhance(2)

    # Rotate the image to its longer side
    if image.width > image.height:
        image = image.rotate(90, expand=True)

    #pal = image.quantize(2)
    
    # Resize the image to 106x314 pixels although the printer only prints 
    # print 96x284 pixels. The printer has non-square pixels, so we
    # need stretch the image to make it look right.
    #image= image.resize((106, 324), Image.NEAREST)
    image.thumbnail((96, 284), Image.NEAREST)



    #image = image.quantize(colors=2, palette=pal, dither=Image.FILTERED)
    image = image.convert('1', dither=Image.FLOYDSTEINBERG)
    image.save("test.png")

    # Convert the image to a bit array
    bitdata = image.tobytes()

    # Pad the bit array to 3408 bytes, so the printe doesnt print black garbage
    if len(bitdata) < 3408:
       bitdata = bitdata.ljust(3408- len(bitdata), b"\xff")

    return bitdata
    
    

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


def send_print_command(data, device):
    try:
        with serial.Serial(device, 115200, timeout=1) as ser:
            ser.write(data)
            in_bin = ser.readline()
            in_hex = in_bin.hex()
            print(in_hex)
    except serial.SerialException as e:
        print(f"Failed to send data via serial connection: {e}")
        return


def build_print_command(imagedata, density, copies):
    serial_data = f"""\033!o\r\n
   SIZE 14.0 mm,40.0 mm\r\n
GAP 5.0 mm,0 mm\r\n
DIRECTION 1,1\r\n
DENSITY {density}\r\n
CLS\r\n
BITMAP 0,0,12,284,1,""".encode()
    serial_data += imagedata

    serial_data += f"""\r\n
PRINT {copies}\r\n""".encode()
    return serial_data

def main():
    parser = argparse.ArgumentParser(description="Print an image on a P21 printer.")
    parser.add_argument("--device", help="The device to print to (defaults to /dev/rfcomm0)", default="/dev/rfcomm0")
    parser.add_argument("--image", help="The image file to print.")
    parser.add_argument("--density", help="The density/darkness of the print (1-15, defaults to 15)", type=int, default=15)
    parser.add_argument("--copies", help="The number of copies to print", type=int, default=1)
    parser.add_argument("--config", help="Get the printer configuration", action="store_true")
    parser.add_argument("--battery", help="Get the printer battery level", action="store_true")
    args = parser.parse_args()

    if args.image:
        bitdata = load_image(args.image)
        print_command = build_print_command(bitdata, args.density, args.copies)
        send_print_command(print_command, args.device)
    if args.config:
        print("Printer configuration:")
        print(get_config())
    if args.battery:
        print("Printer battery status:")
        print(get_battery())

if __name__ == "__main__":
    main()
