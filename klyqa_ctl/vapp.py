#!/usr/bin/env python3

import socket
import sys
import time
import json
import datetime
import argparse
import select

try:
    from Cryptodome.Cipher import AES  # provided by pycryptodome
    from Cryptodome.Random import get_random_bytes  # pycryptodome
except:
    from Crypto.Cipher import AES  # provided by pycryptodome
    from Crypto.Random import get_random_bytes  # pycryptodome


def sendMsg(s):
    print("Sending: " + s)
    plain = s.encode("utf-8")
    while len(plain) % 16:
        plain = plain + bytes([0x20])

    cipher = sendingAES.encrypt(plain)

    while True:
        try:
            con.send(bytes([len(cipher) // 256, len(cipher) % 256, 0, 2]) + cipher)
            return
        except socket.timeout:
            print("Send timed out, retrying...")
            pass


def color_message(red, green, blue, transition, skipWait=False):
    waitTime = transition if not skipWait else 0
    return (
        json.dumps(
            {
                "type": "request",
                "color": {
                    "red": red,
                    "green": green,
                    "blue": blue,
                },
                "transitionTime": transition,
            }
        ),
        waitTime,
    )


def temperature_message(temperature, transition, skipWait=False):
    waitTime = transition if not skipWait else 0
    return (
        json.dumps(
            {
                "type": "request",
                "temperature": temperature,
                "transitionTime": transition,
            }
        ),
        waitTime,
    )


def percent_color_message(red, green, blue, warm, cold, transition, skipWait):
    waitTime = transition if not skipWait else 0
    return (
        json.dumps(
            {
                "type": "request",
                "p_color": {
                    "red": red,
                    "green": green,
                    "blue": blue,
                    "warm": warm,
                    "cold": cold,
                    # "brightness" : brightness
                },
                "transitionTime": transition,
            }
        ),
        waitTime,
    )


def brightness_message(brightness, transition):
    return (
        json.dumps(
            {
                "type": "request",
                "brightness": {
                    "percentage": brightness,
                },
                "transitionTime": transition,
            }
        ),
        transition,
    )


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="virtual App interface")

    parser.add_argument("--color", nargs=3, help="set color command (r,g,b) 0-255")
    parser.add_argument(
        "--temperature",
        nargs=1,
        help="set temperature command (kelvin 1000-12000) (1000:warm, 12000:cold)",
    )
    parser.add_argument("--brightness", nargs=1, help="set brightness in percent 0-100")
    parser.add_argument(
        "--percent_color",
        nargs=5,
        metavar=("RED", "GREEN", "BLUE", "WARM", "COLD"),
        help="set colors and white tones in percent 0 - 100",
    )
    parser.add_argument(
        "--transitionTime", nargs=1, help="transition time in milliseconds", default=[0]
    )
    parser.add_argument(
        "--power", nargs=1, metavar='"on"/"off"', help="turns the bulb on/off"
    )
    parser.add_argument(
        "--party",
        help="blink fast and furious",
        action="store_const",
        const=True,
        default=False,
    )

    parser.add_argument("--myip", nargs=1, help="specify own IP for broadcast sender")
    parser.add_argument("--ota", nargs=1, help="specify http URL for ota")
    parser.add_argument(
        "--ping", help="send ping", action="store_const", const=True, default=False
    )
    parser.add_argument(
        "--request",
        help="send status request",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--factory_reset",
        help="trigger a factory reset on the device (Warning: device has to be onboarded again afterwards)",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--routine_list",
        help="lists stored routines",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--routine_put",
        help="store new routine",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--routine_delete",
        help="delete routine",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--routine_start",
        help="start routine",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--routine_id", help="specify routine id to act on (for put, start, delete)"
    )
    parser.add_argument("--routine_scene", help="specify routine scene label (for put)")
    parser.add_argument("--routine_commands", help="specify routine program (for put)")
    parser.add_argument(
        "--reboot",
        help="trigger a reboot",
        action="store_const",
        const=True,
        default=False,
    )

    parser.add_argument(
        "--passive",
        help="vApp will passively listen vor UDP SYN from devices",
        action="store_const",
        const=True,
        default=False,
    )
    parser.add_argument(
        "--enable_tb", nargs=1, help="enable thingsboard connection (yes/no)"
    )

    if len(sys.argv) < 2:
        parser.print_help()
        sys.exit(1)

    args = parser.parse_args()
    #AES_KEY = bytes([0x00, 0xD0, 0x7B, 0xDC, 0x1F, 0x05, 0x2B, 0x1B, 0x2B, 0x46, 0xD0, 0x3E, 0x94, 0x63, 0x26, 0x13])
    AES_KEY = bytes(
        [
            0x00,
            0x11,
            0x22,
            0x33,
            0x44,
            0x55,
            0x66,
            0x77,
            0x88,
            0x99,
            0xAA,
            0xBB,
            0xCC,
            0xDD,
            0xEE,
            0xFF,
        ]
    )

    tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_address = ("0.0.0.0", 3333)
    tcp.bind(server_address)
    tcp.listen(1)

    udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
    udp.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    if args.myip is not None:
        server_address = (args.myip[0], 2222)
    else:
        server_address = ("0.0.0.0", 2222)
    udp.bind(server_address)

    if args.passive:
        print("Waiting for UDP broadcast")
        data, address = udp.recvfrom(4096)
        print(
            "\n\n 2. UDP server received: ",
            data.decode("utf-8"),
            "from",
            address,
            "\n\n",
        )

        print("3a. Sending UDP ack.\n")
        udp.sendto("QCX-ACK".encode("utf-8"), address)
        time.sleep(1)
        print("3b. Sending UDP ack.\n")
        udp.sendto("QCX-ACK".encode("utf-8"), address)
    else:
        con = None
        while con is None:
            print("Broadcasting QCX-SYN Burst\n")
            udp.sendto("QCX-SYN".encode("utf-8"), ("255.255.255.255", 2222))
            readable, _, _ = select.select([tcp], [], [], 0.1)
            if tcp in readable:
                con, address = tcp.accept()
                print("TCP layer connected")

    # data, address = udp.recvfrom(4096)
    # print("\n\n 2. UDP server received: ", data.decode('utf-8'), "from", address, "\n\n")

    state = "WAIT_IV"
    localIv = get_random_bytes(8)

    sendingAES = None
    receivingAES = None

    message_queue_tx = []

    if args.ota is not None:
        message_queue_tx.append(
            (json.dumps({"type": "fw_update", "url": args.ota}), 3000)
        )

    if args.ping:
        message_queue_tx.append((json.dumps({"type": "ping"}), 10000))

    if args.request:
        message_queue_tx.append((json.dumps({"type": "request"}), 1000))

    if args.enable_tb is not None:
        a = args.enable_tb[0]
        if a != "yes" and a != "no":
            print("ERROR --enable_tb needs to be yes or no")
            sys.exit(1)

        message_queue_tx.append(
            (json.dumps({"type": "backend", "link_enabled": a}), 1000)
        )

    if args.passive:
        pass

    if args.color is not None:
        r, g, b = args.color
        tt = args.transitionTime[0]
        message_queue_tx.append(
            color_message(r, g, b, int(tt), skipWait=args.brightness is not None)
        )

    if args.temperature is not None:
        kelvin = args.temperature[0]
        tt = args.transitionTime[0]
        message_queue_tx.append(
            temperature_message(kelvin, int(tt), skipWait=args.brightness is not None)
        )

    if args.brightness is not None:
        brightness = args.brightness[0]
        tt = args.transitionTime[0]
        message_queue_tx.append(brightness_message(brightness, int(tt)))

    if args.percent_color is not None:
        r, g, b, w, c = args.percent_color
        tt = args.transitionTime[0]
        message_queue_tx.append(
            percent_color_message(
                r, g, b, w, c, int(tt), skipWait=args.brightness is not None
            )
        )

    if args.factory_reset:
        message_queue_tx.append((json.dumps({"type": "factory_reset"}), 500))

    if args.routine_list:
        message_queue_tx.append(
            (json.dumps({"type": "routine", "action": "list"}), 500)
        )

    if args.routine_put:
        message_queue_tx.append(
            (
                json.dumps(
                    {
                        "type": "routine",
                        "action": "put",
                        "id": args.routine_id,
                        "scene": args.routine_scene,
                        "commands": args.routine_commands,
                    }
                ),
                500,
            )
        )

    if args.routine_delete:
        message_queue_tx.append(
            (
                json.dumps(
                    {"type": "routine", "action": "delete", "id": args.routine_id}
                ),
                500,
            )
        )
    if args.routine_start:
        message_queue_tx.append(
            (
                json.dumps(
                    {"type": "routine", "action": "start", "id": args.routine_id}
                ),
                500,
            )
        )

    if args.power:
        message_queue_tx.append(
            (json.dumps({"type": "request", "status": args.power[0]}), 500)
        )

    if args.reboot:
        message_queue_tx.append((json.dumps({"type": "reboot"}), 500))

data = []

message_queue_tx.reverse()
last_send = datetime.datetime.now()
con.settimeout(0.001)
pause = datetime.timedelta(milliseconds=0)
timeout = datetime.timedelta(milliseconds=11000)
elapsed = datetime.datetime.now() - last_send
started = datetime.datetime.now() 
received_finish = False
received_answer = True
while (
    (not received_finish or not received_answer or len(message_queue_tx) > 0 or elapsed < pause)
    and datetime.datetime.now() - started < timeout 
) or args.party:
    try:
        data = con.recv(4096)
        if len(data) == 0:
            print("EOF")
            break
    except socket.timeout:
        pass

    elapsed = datetime.datetime.now() - last_send

    if state == "CONNECTED":
        send_next = elapsed >= pause
        if len(message_queue_tx) > 0 and send_next and received_answer == True:
            msg, ts = message_queue_tx.pop()
            pause = datetime.timedelta(milliseconds=ts)  # ts
            sendMsg(msg)
            received_answer = False
            last_send = datetime.datetime.now()
            elapsed = datetime.datetime.now() - last_send

    if args.party and len(message_queue_tx) < 2:
        r, g, b = get_random_bytes(3)

        brightness = 50
        if args.brightness is not None:
            brightness = int(args.brightness[0])
        tt = 300
        if args.transitionTime is not None:
            tt = int(args.transitionTime[0])
        message_queue_tx.append(color_message(r, g, b, tt, brightness))
        pause = datetime.timedelta(milliseconds=tt)

    while len(data):
        print("TCP server received ", len(data), " bytes from ", address)
        print([hex(b) for b in data])

        pkgLen = data[0] * 256 + data[1]
        pkgType = data[3]

        pkg = data[4 : 4 + pkgLen]
        if len(pkg) < pkgLen:
            print("Incomplete packet, waiting for more...")
            break

        data = data[4 + pkgLen :]

        if state == "WAIT_IV" and pkgType == 0:
            print("Plain: ", pkg)

            con.send(bytes([0, 8, 0, 1]) + localIv)

        if state == "WAIT_IV" and pkgType == 1:
            remoteIv = pkg

            sendingAES = AES.new(AES_KEY, AES.MODE_CBC, iv=localIv + remoteIv)
            receivingAES = AES.new(AES_KEY, AES.MODE_CBC, iv=remoteIv + localIv)

            state = "CONNECTED"

        elif state == "CONNECTED" and pkgType == 2:
            received_finish = True
            received_answer = True
            cipher = pkg

            plain = receivingAES.decrypt(cipher)

            print("Decrypted: ", plain)
