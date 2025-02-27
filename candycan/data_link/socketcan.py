# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/04.data_link.socketcan.ipynb.

# %% auto 0
__all__ = ['pp', 'repo', 'done', 'get_argparser', 'signal_usr1', 'send_msg', 'receive_message']

# %% ../../nbs/04.data_link.socketcan.ipynb 3
# from multiprocessing import Process, Event
# from multiprocessing import synchronize, Manager
# from multiprocessing.managers import DictProxy
from pprint import pprint, PrettyPrinter
import subprocess
import threading
from datetime import datetime
import json
import argparse
import os
import git
import sys
import signal
import time
from multiprocessing import Manager
from multiprocessing.managers import DictProxy

# %% ../../nbs/04.data_link.socketcan.ipynb 4
import can

# from can.interface import Bus
# from can import Message
import cantools
from cantools.database import Message as MessageTpl
from cantools.database.can.database import Database

# %% ../../nbs/04.data_link.socketcan.ipynb 5
pp = PrettyPrinter(indent=4, width=80, compact=True)

# %% ../../nbs/04.data_link.socketcan.ipynb 7
repo = git.Repo("./", search_parent_directories=True)  # get the Repo object of tspace
if os.path.basename(repo.working_dir) != "candycan":  # I'm in the parent repo!
    repo = repo.submodule("candycan").module()
pprint(repo.working_dir)

# %% ../../nbs/04.data_link.socketcan.ipynb 8
def get_argparser() -> argparse.ArgumentParser:
    """_summary_ get CAN bus, dbc config and the message to send

    Returns:
        argparse.ArgumentParser: _description_
    """

    parser = argparse.ArgumentParser("Get the CAN Bus channel, bitrate and dbc path")

    parser.add_argument(
        "-t",
        "--type",
        type=str,
        default="socketcan",
        help="The type of the CAN bus",
    )

    parser.add_argument(
        "-c",
        "--channel",
        type=str,
        default="vcan0",
        help="The CAN bus channel to connect to",
    )

    parser.add_argument(
        "-b", "--bitrate", type=int, default=250000, help="The bitrate of the CAN bus"
    )

    parser.add_argument(
        "-d",
        "--dbc",
        type=str,
        default="../../res/motohawk_new.dbc",
        help="The path to the dbc file",
    )

    parser.add_argument(
        "-m",
        "--message",
        type=str,
        default="ExampleMessage",
        help="The message to send",
    )

    parser.add_argument(
        "-e",
        "--extended",
        action="store_true",
        help="If the arbitration id is extended",
    )

    return parser

# %% ../../nbs/04.data_link.socketcan.ipynb 9
done = threading.Event()


def signal_usr1(signum, frame):
    """Handle USR1 signal as an event to set the received flag."""
    # global received
    # received = True

    done.set()
    # print("received signal, sending done!")

# %% ../../nbs/04.data_link.socketcan.ipynb 10
def send_msg(
    db: Database,
    message: str,
    payload: bytes,
    channel: str,
    bitrate: int,
    bus_type: str,
    is_extended: bool,
) -> None:
    """
    send a CAN frame with bytes interface, the multiprocessing interface has to use PIPE which is character based.
    """
    message_definition = db.get_message_by_name(message)
    data_dict = json.loads(payload.decode())

    # print("Prepare sending message")
    sys.stdout.flush()
    can_data = message_definition.encode(data_dict)
    message = can.Message(
        arbitration_id=message_definition.frame_id,
        data=can_data,
        is_extended_id=is_extended,
    )
    # print(message)
    # print("Before sending message")
    with can.interface.Bus(bustype=bus_type, channel=channel, bitrate=bitrate) as bus:
        bus.send(message)

# %% ../../nbs/04.data_link.socketcan.ipynb 17
def receive_message(message_proxy: DictProxy, bus: can.interface.Bus) -> None:
    print("waiting for message")
    msg: can.Message = bus.recv()
    print("message received")
    message_proxy["timestamp"] = msg.timestamp
    message_proxy["arbitration_id"] = msg.arbitration_id
    message_proxy["data"] = msg.data

# %% ../../nbs/04.data_link.socketcan.ipynb 26
if (
    __name__ == "__main__" and "__file__" in globals()
):  # in order to be compatible for both script and notebnook

    # print(os.getcwd())
    p = get_argparser()
    args = p.parse_args()
    # args = p.parse_args(
    #     [
    #         "--type",
    #         "socketcan",
    #         "--channel",
    #         "vcan0",
    #         "--bitrate",
    #         "250000",
    #         "--dbc",
    #         "./examples/motohawk_new.dbc",
    #         "--message",
    #         "ExampleMessage",
    #     ]
    # )
    # print(args)

    try:
        db: Database = cantools.database.load_file(args.dbc)
    except FileNotFoundError as e:
        print(f"File not found: {e}")

    payload = sys.stdin.buffer.read()

    send_msg(
        db=db,
        message=args.message,
        payload=payload,
        channel=args.channel,
        bitrate=args.bitrate,
        bus_type=args.type,
        is_extended=args.extended,
    )

    signal.signal(signal.SIGUSR1, signal_usr1)
    # print("set message handler and sleep")
    sys.stdout.flush()
    now = time.time()
    done.wait()
    time_lapsed = time.time() - now
    print(f"Signal received after {time_lapsed:.3f} seconds")
