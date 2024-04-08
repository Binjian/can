# AUTOGENERATED! DO NOT EDIT! File to edit: ../../nbs/vcantest/ccp.socketcan.ipynb.

# %% auto 0
__all__ = ['pp', 'repo', 'BUS_TYPES', 'BusType', 'ccp_command', 'get_argparser', 'check_bus_type', 'CANFilter', 'ScapyCANSpecs',
           'CCPCommand', 'npa_to_packed_buffer', 'flash_xcp', 'can_context', 'SET_MTA_context', 'XLOAD_context',
           'upload_calib_data2', 'downlod_calib_data2']

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 5
import os
import sys
import git
import argparse
from InquirerPy import inquirer
from InquirerPy.validator import EmptyInputValidator
from InquirerPy.base.control import Choice
from pydantic import BaseModel, Field,  ConfigDict, model_validator, conlist, conint, computed_field, confloat, ValidationError
from pydantic.functional_validators import AfterValidator
from typing import Optional, TypedDict, Union, Literal
from typing_extensions import Annotated
from enum import StrEnum
from pprint import pprint, PrettyPrinter

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 6
import subprocess
from multiprocessing import Manager
from multiprocessing.managers import DictProxy
import can
from cantools.database import Message as MessagerTpl
from cantools.database.can.database import Database
import contextlib

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 7
import pandas as pd
import numpy as np
import struct

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 9
from candycan.a2l import (
    list_of_strings,
    XCPCalib,
    XCPData,
    XCPConfig,
    Get_XCPCalib_From_XCPJSon,
    Generate_Init_XCPData_From_A2L,
)


# %% ../../nbs/vcantest/ccp.socketcan.ipynb 10
# from scapy.all import (
#     raw, rdpcap, wrpcap, load_contrib, hexdump,
#     ls, conf, load_layer, IP, Ether, TCP
# )
# Ether, TCP, hexdump, raw, rdpcap, load_contrib, conf, load_layer, 
# CANSocket, CAN, wrpcap, CCP, CRO, CONNECT, GET_SEED, UNLOCK, GET_DAQ_SIZE
from candycan.data_link.socketcan import (
    send_msg, done, signal_usr1, receive_message
)

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 12
pp = PrettyPrinter(indent=4, width=80, compact=True)

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 13
repo = git.Repo("./", search_parent_directories=True)  # get the Repo object of tspace
if os.path.basename(repo.working_dir) != "candycan":  # I'm in the parent repo!
    repo = repo.submodule("candycan").module()
pprint(repo.working_dir)

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 14
def get_argparser() -> argparse.ArgumentParser:
	"""Summary
	Get argument parser for command line arguments

	Returns:
		argparse.ArgumentParser: _description_
	"""
	parser = argparse.ArgumentParser(description='XCP Processing')

	parser.add_argument(
		'--protocol',
		type=str,
		choices=['CCP', 'XCP'],
		default='CCP',
		help='Protocol to use: CCP/XCP',
	)

	parser.add_argument(
		'--bus_type',
		type=str,
		choices=['SOCKET', 'VIRTUAL'],
		default='SOCKET',
		help='Bus type to use: SOCKET/VIRTUAL',
	)

	parser.add_argument(
		'--download',
		default=False,
		help='Download or upload: default is download(host->target)',
		action='store_true',
	)

	parser.add_argument(
		'--diff_mode',
		default=True,
		help='use differential mode for flashing',
		action='store_true',
	)

	parser.add_argument(
		'--diff_threshold',
		type=float,
		default=0.001,
		help='Threshold as different float value for differential mode',
	)

	parser.add_argument(
		'--bit_rate',
		type=int,
		choices=range(1_000_000),
		default=500_000,
		help='Bit rate for CAN bus, maximal 1Mbps',
	)

	parser.add_argument(
		'--time_out',
		type=float,
		default=1.0,
		help='Time out for CAN bus response',
	)

	parser.add_argument(
		"--station_address",
		type=int,
		default=0,  # 0 for all except for MOVE, which should be 1
		help='Station address of ECU for CCP protocol, MTA number 0/1',
	)

	parser.add_argument(
		"--download_can_id",
		type=int,
		default=630,
		help='Download CAN message ID for CCP protocol',
	)

	parser.add_argument(
		"--upload_can_id",
		type=int,
		default=631,
		help='Upload CAN message ID for CCP protocol',
	)

	parser.add_argument(
		'--a2l', 
		type=str,
        default=repo.working_dir+'/res/VBU_AI.json',
		help='a2l json file path')

	parser.add_argument(
		"--node-path",
		type=str,
		default=r"/PROJECT/MODULE[]",
		help="node path to search for calibration parameters",
	)

	parser.add_argument(
		"--leaves",
		type=list_of_strings,
		default=r"TQD_trqTrqSetNormal_MAP_v, " 
				r"VBU_L045A_CWP_05_09T_AImode_CM_single, " 
				r"Lookup2D_FLOAT32_IEEE, " 
				r"Lookup2D_X_FLOAT32_IEEE, " 
				r"Scalar_FLOAT32_IEEE, " 
				r"TQD_vVehSpd, "
				r"TQD_vSgndSpd_MAP_y, "
				r"TQD_pctAccPedPosFlt, "
				r"TQD_pctAccPdl_MAP_x",
			help="leaf nodes to search for",
	)

	parser.add_argument(
		'--channel_serial_number', 
		type=int,
		default=3,
		help='CAN channel serial number for flashing')

	parser.add_argument(
		'--input', 
		type=str,
        default=repo.working_dir+'/res/download.json',
		help='Input file path')

	parser.add_argument(
		'--output', 
		type=str, 
        default=repo.working_dir+'/res/output.json',
		help='Output file path')
	return parser

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 19
BUS_TYPES = set(['SOCKET', 'VIRTUAL'])
# class BusType(StrEnum):
#     SOCKET = "SOCKET"
#     VIRTUAL = "VIRTUAL"

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 20
def check_bus_type(b: str) -> str:
    """Summary
    Check if the CAN bus type is valid

    Args:
        b (str): Python CAN bus type to be checked

    Returns:
        str: Python CAN bus type if valid

    Raises:
        ValueError: if CAN bus type is invalid
    """
    if b.upper() not in BUS_TYPES:
        raise ValueError(f"Invalid Python CAN bus type: {b}, valid types are: {BUS_TYPES}")
    return b

BusType = Annotated[str, AfterValidator(check_bus_type)]

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 21
class CANFilter(BaseModel):
    """Summary
    CAN filter for Python CAN bus

    Attributes:
        can_id (int): CAN message ID
        can_mask (int): CAN message mask
    """
    can_id: int = Field(default=630,gt=0,title="CAN message ID",description="CAN message ID")
    can_mask: int = Field(default=0x7ff,gt=0,title="CAN message mask",description="CAN message mask")

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 22
class ScapyCANSpecs(BaseModel):
    bus_type: BusType = Field(frozen=True, default='VIRTUAL', description='Python CAN bus type')
    channel_serial_number: int = Field(frozen=True, default=3, ge=0, lt=500,description='CAN channel')
    download_can_id: int = Field(default=630, gt=0, description='Download CAN message ID')
    upload_can_id: int = Field(default=630, gt=0, description='Upload CAN message ID')
    can_filters: Optional[list[CANFilter]] = Field(default=None, description='CAN filters')
    bit_rate: int = Field(default=500_000, gt=0, lt=1_000_000, description='CAN bit rate')
    time_out: float = Field(default=1.0, gt=0.0, lt=10.0, description='CAN time out')
    station_address: int = Field(default=0x00, ge=0, lt=0xff, description='CAN station address')
    cntr: int = Field(default=0, ge=0, lt=1_000_000, description='CAN counter')
    receive_own_messages: bool = Field(default=True, description='Receive own messages')
    download_upload: bool = Field(default=True, description='Download if True or upload if False')
    diff_mode: bool = Field(default=False, description='Differential flashing (download)')
    diff_threshold: float = Field(default=1e-3, description='Threshold for float value difference')
    last_download_data: Optional[XCPData] = Field(default=None, description='Last download data')
    
    @computed_field
    def channel(self) -> Union[str, int]:
        """Summary
        Get the CAN channel as str for SocketCAN or virtual CAN, as int for Vector

        Returns:
            str: CAN channel for SocketCAN virtual CAN
            int: for Vector CAN
        """
        match self.bus_type:
            case 'VIRTUAL':
                return 'vcan' + str(self.channel_serial_number)
            case 'SOCKET':
                return 'can' + str(self.channel_serial_number)
            case 'VECTOR' | "KVASER":
                return self.channel_serial_number
            case 'PCAN':
                return 'PCAN_USBBUS' + str(self.channel_serial_number)
            case _:
                raise NotImplementedError(f"Bus type: {self.bus_type} not implemented yet")
                


# %% ../../nbs/vcantest/ccp.socketcan.ipynb 26
class CCPCommand(BaseModel):
    connect: int = Field(default=0x01, frozen=True, description='CCP connect command')
    set_mta: int = Field(default=0x02, frozen=True, description='CCP set memory transfer address command')
    disconnect: int = Field(default=0x07, frozen=True, description='CCP disconnect command')
    download: int = Field(default=0x03, frozen=True, description='CCP download command DNLOAD')
    download6: int = Field(default=0x23, frozen=True, description='CCP download command DNLOAD6')
    upload: int = Field(default=0x04, frozen=True, description='CCP upload command UPLOAD')
    short_upload: int = Field(default=0x0F, frozen=True, description='CCP short upload command SHORT_UP')
    get_seed: int = Field(default=0x12, frozen=True, description='CCP get seed command GET_SEED')
    get_ccp_version:  int = Field(default=0x1B, frozen=True, description='CCP get CCP version command GET_CCP_VERSION')
    
        # 0x01: "CONNECT",
        # 0x1B: "GET_CCP_VERSION",
        # 0x17: "EXCHANGE_ID",
        # 0x12: "GET_SEED",
        # 0x13: "UNLOCK",
        # 0x02: "SET_MTA",
        # 0x03: "DNLOAD",
        # 0x23: "DNLOAD_6",
        # 0x04: "UPLOAD",
        # 0x0F: "SHORT_UP",
        # 0x11: "SELECT_CAL_PAGE",
        # 0x14: "GET_DAQ_SIZE",
        # 0x15: "SET_DAQ_PTR",
        # 0x16: "WRITE_DAQ",
        # 0x06: "START_STOP",
        # 0x07: "DISCONNECT",
        # 0x0C: "SET_S_STATUS",
        # 0x0D: "GET_S_STATUS",
        # 0x0E: "BUILD_CHKSUM",
        # 0x10: "CLEAR_MEMORY",
        # 0x18: "PROGRAM",
        # 0x22: "PROGRAM_6",
        # 0x19: "MOVE",
        # 0x05: "TEST",
        # 0x09: "GET_ACTIVE_CAL_PAGE",
        # 0x08: "START_STOP_ALL",
        # 0x20: "DIAG_SERVICE",
        # 0x21: "ACTION_SERVICE"

ccp_command =  CCPCommand()
ccp_command.model_dump()

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 38
def npa_to_packed_buffer(a: np.ndarray) -> str:
    """ convert a numpy array to a packed string buffer for flashing
    TODO: implementation as numpy ufunc

    Args:
        a (np.ndarray): input numpy array for flashing

    Returns:
        str: packed string buffer for flashing
    """
    b = [struct.pack("<f", x).hex() for x in np.nditer(a)]
    return ''.join(b)

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 42
def flash_xcp(xcp_calib: XCPCalib, data: pd.DataFrame, diff_flashing: bool=False, download: bool=True):
    """Summary
    Flash XCP data to target

    Args:
        xcp_calib (XCPCalib): XCP calibration as template, contains all the meta information except for data
        xcp_data (pd.DataFrame): input XCP data to be flashed, replace the value in xcp_calib
        diff_flashing (bool): Use differential flashing
        download (bool): Download or upload
    
    """
    
    # convert dataframe to a hex string to be flashed and assigned to XCPCalib field data
    xcp_calib.data = data.astype(np.float32).tobytes().hex()

    if download:
        if diff_flashing:
            raise NotImplementedError("Differential flashing not implemented yet")
        else:
            pass
        

    

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 103
@contextlib.contextmanager
def can_context(can_specs: ScapyCANSpecs):
    """Summary
    Context manager for scapy CAN socket

    Args:
        can_specs (ScapyCANSpecs): CAN specs including can type, bus type, channel, etc.

    Yields:
        Bus: Python-CAN Bus object
    """
    # create a socket
 

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 104
@contextlib.contextmanager
def SET_MTA_context(can_specs: ScapyCANSpecs, bus: can.interface.Bus, data: XCPData):
    """Summary
    Context manager for scapy set_mta 

    Args:
        channel (str): CAN channel to use, default is vcan0

    Yields:
        CAN: packdet for CAN message 
    """

    # SET_MTA 
    # cro = CCP(identifier=can_specs.download_can_id)/CRO(ctr=can_specs.cntr)/SET_MTA(address=int(data.address, 16))
    # dto = sock.sr1(cro, timeout=can_specs.time_out)
    # assert dto.return_code == 0x00
    # can_specs.cntr += 1
    # try:
    #     yield dto
    # except TimeoutError:
    #     raise TimeoutError(f"CAN socket timeout: {can_specs.time_out} seconds")
    # except Exception as e:
    #     raise e
    # finally:
    #     pass  # do nothing, just pray it'll be OK. Crapy CCP!
    


# %% ../../nbs/vcantest/ccp.socketcan.ipynb 105
@contextlib.contextmanager
def XLOAD_context(can_specs: ScapyCANSpecs, bus: can.interface.Bus, data: XCPData, start_index: int, tile_size: int):
    """Summary
    Context manager for scapy load (download or upload)

    Args:
        channel (str): CAN channel to use, default is vcan0

    Yields:
        CANSocket: CAN socket object
    """
    pass

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 107
def upload_calib_data2(xcp_calib: XCPCalib, 
                        can_specs: ScapyCANSpecs
                        )->None:

    """Summary
    Upload XCP calibration data from target to host, the result will update the xcp_calib.data field

    Args:
        xcp_calib (XCPCalib): XCP calibration  to be uploaded from the target to host
        diff_flashing (bool): Use differential flashing
    """

    # init counter
    cntr = 0
    pass

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 108
def downlod_calib_data2(xcp_calib: XCPCalib, 
                        can_specs: ScapyCANSpecs
                        )->None:
    """Summary
    Download XCP calibration data to target use scapy_can_context

    Args:
        xcp_calib (XCPCalib): XCP calibration  to be downloaded into the target
    """

    assert can_specs.download_upload==True, f"Check can_specs.download_upload flag, it should be True for download"
    if can_specs.diff_mode :
        if can_specs.last_download_data is None:  # diff mode in the first run, needs to upload first to populate last_download_data
            last_xcp_calib = XCPCalib(config=xcp_calib.config, data=xcp_calib.data)
            can_specs.download_upload = False
            upload_calib_data2(xcp_calib=last_xcp_calib, can_specs=can_specs)
            can_specs.last_download_data = last_xcp_calib.data
            can_specs.download_upload = True
        # calculate the difference between the last downloaded data and the current data
        assert len(can_specs.last_download_data)==len(xcp_calib.data), "XCPData list length is not the same"
        data_pair = zip(can_specs.last_download_data, xcp_calib.data)
        xcp_data = []
        for d0, d1 in zip(xcp_calib.data, can_specs.last_download_data):
            assert d0.is_compatible(d1), f"incompatible data {d0} vs {d1}"
            diff_array_index_2d = np.where((d0.value_array_view - d1.value_array_view) > can_specs.diff_threshold)
            diff_array_index_1d = np.ravel_multi_index(diff_array_index_2d, d0.dim, order='C')
            diff_array_value = d0[diff_array_index_2d]
            diff_array_address = d0.address_int + diff_array_index_1d * d0.type_size
            
            xcp_data += [XCPData(address=hex(address), 
                                value=value, 
                                name=d0.name, 
                                dim=d0.dim, 
                                value_type=d0.value_type, 
                                value_length=d0.value_length
                                ) 
                            for address, value in zip(diff_array_address, diff_array_value)
                        ]
    else:  # non-diff mode 
        xcp_data = xcp_calib.data
        
    try:
        pass
        # with can_context(can_specs=can_specs) as sock:
        #     for d in xcp_data:
        #         # SET_MTA
        #         with SET_MTA_context(can_specs=can_specs, sock=sock, data=d) as dto:
        #             assert dto.return_code==0x00, f"SET_MTA failed for {d.name} at {d.address}"
        #             # Determine message tiling
        #             len_in_bytes = d.type_size * d.dim[0] * d.dim[1]
        #             assert len_in_bytes == len(d.value_bytes)
        #             tile_size = 6  # 6 bytes per tile as defined in CCP for DNLOAD_6
        #             tiles = len_in_bytes //tile_size 
        #             last_tile = len_in_bytes % tile_size
        #             # Download full size tiles with DNLOAD_6
        #             for i in range(tiles):
        #                 start_index = i*tile_size
        #                 with XLOAD_context(can_specs=can_specs, sock=sock, data=d, start_index=start_index, tile_size=tile_size) as dto:
        #                     assert dto.return_code == 0x00, f"DNLOAD_6 failed at tile: {i}"

        #             start_index = tiles * tile_size
        #             with XLOAD_context(can_specs=can_specs, sock=sock, data=d, start_index=start_index, tile_size=last_tile) as dto:
        #                 assert dto.return_code == 0x00, f"DNLOAD failed at last tile: {i} of size {last_tile}"
    except Exception as e:
        print(e)
    
    # keep the last downloaded data for diff mode
    can_specs.last_download_data = xcp_calib.data

# %% ../../nbs/vcantest/ccp.socketcan.ipynb 119
if __name__ == "__main__" and "__file__" in globals():  # only run if this file is called directly

    protocol = inquirer.select(
        message="What's the protocol?",
        choices=[
            Choice(value="CCP", name="CCP"),
            Choice(value="XCP", name="XCP"),
        ],
        default="CCP",
    ).execute()

    can = inquirer.select(
        message="What's the type of CAN?",
        choices=[
            Choice(value="NATIVE", name="Native Linux SocketCAN"),
            Choice(value="PYTHON", name="Python CAN"),
        ],
        default="NATIVE",
    ).execute()

    if can == 'NATIVE':
        bus = inquirer.select(
            message="What's the type of bus?",
            choices=[
                Choice(value="SOCKET", name="Physical CAN"),
                Choice(value="VIRTUAL", name="Virtual CAN"),
            ],
            default="SOCKET",
        ).execute()
    else:  # can == 'PYTHON'
        bus = inquirer.select(
            message="What's the type of bus?",
            choices=[
                Choice(value="SOCKET", name="Physical SocketCAN"),
                Choice(value="VIRTUAL", name="Virtual SocketCAN"),
                Choice(value="KVASER", name="Kvaser CAN"),
            ],
            default="SOCKET",
        ).execute()

    download = inquirer.confirm(
        message="Downloading(host->target)?",
        confirm_letter="y",
        reject_letter="n",
        default=True,
    ).execute()

    differential_flashing = inquirer.confirm(
        message="Differential Flashing?",
        confirm_letter="y",
        reject_letter="n",
        default=True,
    ).execute()

    a2l_file_path = inquirer.text(
        message="a2l file path",
        validate=EmptyInputValidator(),
        default='/res/vbu_ai.json'
    ).execute()

    # node_path = inquirer.text(
    #     message="node path",
    #     validate=EmptyInputValidator(),
    # 	default=r"/PROJECT/MODULE[]",
    # ).execute()

    # leaves = inquirer.text(
    #     message="leaves",
    #     validate=EmptyInputValidator(),
    # 	default=r"TQD_trqTrqSetNormal_MAP_v, VBU_L045A_CWP_05_09T_AImode_CM_single, Lookup2D_FLOAT32_IEEE, Lookup2D_X_FLOAT32_IEEE, Scalar_FLOAT32_IEEE, TQD_vVehSpd, TQD_vSgndSpd_MAP_y, TQD_pctAccPedPosFlt, TQD_pctAccPdl_MAP_x"
    # ).execute()

    # can_channel = inquirer.number(
    #     message="CAN channel for flashing",
    #     min_allowed=0,
    #     max_allowed=32,
    #     validate=EmptyInputValidator(),
    #     default=3,
    # ).execute()

    input_file_path = inquirer.text(
        message="Input file path",
        validate=EmptyInputValidator(),
        default="/res/download.json",
    ).execute()

    output_file_path = inquirer.text(
        message="Output file path",
        validate=EmptyInputValidator(),
        default="/res/output.json",
    ).execute()

    args = get_argparser().parse_args()
    args.protocol = protocol
    args.can_type = can
    args.bus_type = bus
    args.download = download
    args.diff_mode = differential_flashing
    # args.a2l = a2l_file_path
    # args.node_path = node_path
    # args.leaves = leaves
    args.input = repo.working_dir+input_file_path
    args.output = repo.working_dir+output_file_path
    pprint(args)

    xcp_calib_from_xcpjson = Get_XCPCalib_From_XCPJSon(args.input)

    args.download_can_id = xcp_calib_from_xcpjson.config.download_can_id
    args.upload_can_id = xcp_calib_from_xcpjson.config.upload_can_id
    args.channel_serial_number = xcp_calib_from_xcpjson.config.channel

    xcp_data = Generate_Init_XCPData_From_A2L(
        a2l=args.a2l, keys=args.leaves, node_path=args.node_path
    )  # initial xcp_data has value 0
    try:
        XCPData.model_validate(xcp_data)
    except ValidationError as exc:
        print(exc)

    # emulate torque table input as numpy array
    xcp_data_value_npa = xcp_calib_from_xcpjson.data[0].value_array_view
    xcp_data.value = xcp_data_value_npa.astype(np.float32).tobytes().hex()
    pprint(xcp_data)

    xcp_calib = XCPCalib(
        config=XCPConfig(
            channel=args.channel_serial_number, download=args.download_can_id, upload=args.upload_can_id
        ),
        data=[xcp_data],
    )
    pprint(xcp_calib)

    can_filters = [{'can_id': xcp_calib.config.upload_can_id, 'can_mask': 0x7FF}]
    cntr = 0
    can_specs = ScapyCANSpecs(can_type=args.can_type,
                            bus_type=args.bus_type,
                            channel_serial_number=args.channel_serial_number,
                            download_can_id=xcp_calib.config.download_can_id,
                            upload_can_id=xcp_calib.config.upload_can_id,
                            can_filters=can_filters,
                            bit_rate=args.bit_rate,
                            time_out=args.time_out,
                            station_address=args.station_address,
                            cntr=cntr,
                            receive_own_messages=True,
                            download_upload=args.download,  # CCP Upload mode
                            diff_mode = args.diff_mode,
                            diff_threshold= args.diff_threshold
                            )
    can_specs.download_upload = False                        
    upload_calib_data2(xcp_calib=xcp_calib, can_specs=can_specs)
    can_specs.download_upload = True                       
    downlod_calib_data2(xcp_calib=xcp_calib,can_specs=can_specs)
    
