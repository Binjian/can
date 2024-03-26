# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02.ccp.ipynb.

# %% auto 0
__all__ = ['pp', 'repo', 'CAN_TYPES', 'CANType', 'BUS_TYPES', 'BusType', 'get_argparser', 'npa_to_packed_buffer', 'flash_xcp',
           'check_can_type', 'check_bus_type', 'CANFilter', 'ScapyCANSpecs', 'downlod_calib_data', 'upload_calib_data',
           'scapy_can_context', 'scapy_SET_MTA_context', 'scapy_load_context', 'downlod_calib_data2',
           'upload_calib_data2']

# %% ../nbs/02.ccp.ipynb 3
import os
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

# %% ../nbs/02.ccp.ipynb 4
import subprocess
from multiprocessing import Manager
from multiprocessing.managers import DictProxy
import cantools
from cantools.database import Message as MessagerTpl
from cantools.database.can.database import Database
import contextlib

# %% ../nbs/02.ccp.ipynb 5
import pandas as pd
import numpy as np
import struct

# %% ../nbs/02.ccp.ipynb 7
from candycan.a2l import (
    list_of_strings,
    XCPCalib,
    XCPData,
    XCPConfig,
    Get_XCPCalib_From_XCPJSon,
    Generate_Init_XCPData_From_A2L,
)


# %% ../nbs/02.ccp.ipynb 8
from scapy.all import (
    raw, rdpcap, wrpcap, load_contrib, hexdump,
    ls, conf, load_layer, IP, Ether, TCP
)
# Ether, TCP, hexdump, raw, rdpcap, load_contrib, conf, load_layer, 
# CANSocket, CAN, wrpcap, CCP, CRO, CONNECT, GET_SEED, UNLOCK, GET_DAQ_SIZE

# %% ../nbs/02.ccp.ipynb 9
load_layer("can")  # CAN
conf.contribs['CANSocket'] = {'use-python-can': False}
load_contrib("cansocket") # CANSocket
load_contrib("automotive.ccp")  # CCP, CRO, CONNECT, DISCONNECT, GET_SEED, UNLOCK, GET_DAQ_SIZE

# %% ../nbs/02.ccp.ipynb 10
pp = PrettyPrinter(indent=4, width=80, compact=True)

# %% ../nbs/02.ccp.ipynb 11
repo = git.Repo("./", search_parent_directories=True)  # get the Repo object of tspace
if os.path.basename(repo.working_dir) != "candycan":  # I'm in the parent repo!
    repo = repo.submodule("candycan").module()
pprint(repo.working_dir)

# %% ../nbs/02.ccp.ipynb 12
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
		choices=['ccp', 'xcp'],
		default='ccp',
		help='Protocol to use: ccp/xcp',
	)

	parser.add_argument(
		'--download',
		default=False,
		help='Download or upload: default is download(host->target)',
		action='store_true',
	)

	parser.add_argument(
		'--diff_flashing',
		default=True,
		help='use differential flashing',
		action='store_false',
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
		'--channel', 
		type=int,
		default=3,
		help='CAN channel for flashing')
		
	parser.add_argument(
		'--download_id', 
		type=int,
		default=630,
		help='CAN message ID for downloading')
		
	parser.add_argument(
		'--upload_id', 
		type=int,
		default=631,
		help='CAN message ID for downloading')
		
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

# %% ../nbs/02.ccp.ipynb 27
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

# %% ../nbs/02.ccp.ipynb 30
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
        

    

# %% ../nbs/02.ccp.ipynb 70
CAN_TYPES = set(['NATIVE','PYTHON'])  # Navtive: Native CAN: PYTHON: Python CAN
# class CanType(StrEnum):
#     NATIVE = "NATIVE"
#     PYTHON = "PYTHON"
CAN_TYPES

# %% ../nbs/02.ccp.ipynb 71
def check_can_type(c: str) -> str:
    """Summary
    Check if the CAN type is valid

    Args:
        can_type (str): CAN type to be checked

    Returns:
        str: CAN type if valid

    Raises:
        ValueError: if CAN type is invalid
    """
    if c.upper() not in CAN_TYPES:
        raise ValueError(f"Invalid CAN type: {c}, valid types are: {CAN_TYPES}")
    return c

CANType = Annotated[str, AfterValidator(check_can_type)]

# %% ../nbs/02.ccp.ipynb 73
BUS_TYPES = set(['SOCKET', 'VIRTUAL', 'KVASER', 'PCANUSB', 'IXXAT', 'VECTOR', 'SERIAL', 'NEOVI'])
# class BusType(StrEnum):
#     SOCKET = "SOCKET"
#     VIRTUAL = "VIRTUAL"
#     KVASER = "KVASER"
#     PCANUSB = "PCANUSB"
#     IXXAT = "IXXAT"
#     VECTOR = "VECTOR"
#     SERIAL = "SERIAL"
#     NEOVI = "NEOVI"


# %% ../nbs/02.ccp.ipynb 74
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

# %% ../nbs/02.ccp.ipynb 75
class CANFilter(BaseModel):
    """Summary
    CAN filter for Python CAN bus

    Attributes:
        can_id (int): CAN message ID
        can_mask (int): CAN message mask
    """
    can_id: int = Field(default=630,gt=0,title="CAN message ID",description="CAN message ID")
    can_mask: int = Field(default=0x7ff,gt=0,title="CAN message mask",description="CAN message mask")

# %% ../nbs/02.ccp.ipynb 76
class ScapyCANSpecs(BaseModel):
    can_type: CANType = Field(frozen=True, default='NATIVE', description='CAN type: NATIVE/PYTHON')
    bus_type: BusType = Field(frozen=True, default='VIRTUAL', description='Python CAN bus type')
    channel_serial_number: int = Field(frozen=True, default=3, ge=0, lt=500,description='CAN channel')
    can_id: int = Field(default=630, gt=0, description='CAN message ID')
    can_filters: Optional[list[CANFilter]] = Field(default=None, description='CAN filters')
    bit_rate: int = Field(default=500_000, gt=0, lt=1_000_000, description='CAN bit rate')
    time_out: float = Field(default=1.0, gt=0.0, lt=10.0, description='CAN time out')
    station_address: int = Field(default=0x00, ge=0, lt=0xff, description='CAN station address')
    cntr: int = Field(default=0, ge=0, lt=1_000_000, description='CAN counter')
    receive_own_messages: bool = Field(default=True, description='Receive own messages')
    download_upload: bool = Field(default=True, description='Download if True or upload if False')
    
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
                


# %% ../nbs/02.ccp.ipynb 80
def downlod_calib_data(xcp_calib: XCPCalib, 
                        can_type: CANType, 
                        channel: int,
                        bus_type: BusType, 
                        can_filter=list[dict],  
                        bit_rate: int=500_000, 
                        timeout: float=1.0,
                        diff_flashing: bool=False):
    """Summary
    Download XCP calibration data to target

    Args:
        xcp_calib (XCPCalib): XCP calibration  to be downloaded into the target
        diff_flashing (bool): Use differential flashing
    """
    # init counter
    ctr = 0
    # create a socket
    match can_type:
        case 'NATIVE':
            load_layer("can")
            conf.contribs['CANSocket'] = {'use-python-can': False}
            load_contrib("cansocket")
            match bus_type:
                case 'SOCKET':
                    sock = CANSocket(channel='can'+str(channel), can_filter=can_filter, bit_rate = bit_rate, receive_own_messages=True)
                case 'VIRTUAL':
                    sock = CANSocket(channel='vcan'+str(channel), can_filter=can_filter, bit_rate = bit_rate, receive_own_messages=True)
                case _:
                    raise ValueError(f"Invalid CAN bus type: {bus_type}, valid types are: SOCKET or VIRTUAL for Native CANSOCKET")
        case 'PYTHON': 
            assert bus_type is not None, "Bus type must be specified for PYTHON CAN"
            load_layer("can")
            conf.contribs['CANSocket'] = {'use-python-can': True}
            load_contrib("cansocket")
            match bus_type:
                case 'SOCKET':
                    sock = CANSocket(bustype='socketcan', channel='can'+channel, can_filter=can_filter, bitrate=bit_rate, receive_own_messages=True)
                case 'VIRTUAL':
                    sock = CANSocket(bustype='socketcan', channel='vcan'+channel, can_filter=can_filter, bitrate=bit_rate, receive_own_messages=True)
                case 'KVASER':
                    sock = CANSocket(bustype='kvaser', channel=channel, can_filter=can_filter, bitrate=bit_rate, receive_own_messages=True)
                case 'VECTOR':
                    sock = CANSocket(bustype='vector', channel=channel, can_filter=can_filter, bitrate=bit_rate, receive_own_messages=True)
                case _:
                    raise ValueError(f"Invalid CAN bus type: {bus_type}, implemented valid types are: SOCKET, KVASER, VECTOR for Python-CAN CANSOCKET")

    # CONNECT
    ctr += 1
    cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/CONNECT(station_address=0x00)
    dto = sock.sr1(cro, timeout=timeout)
    assert dto.return_code == 0x00

    for d in xcp_calib.data:
        # SET_MTA
        ctr += 1
        cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/SET_MTA(address=int(d.address, 16))
        dto = sock.sr1(cro, timeout=timeout)
        assert dto.return_code == 0x00

        # Determine message tiling
        len_in_bytes = d.type_size * d.dim[0] * d.dim[1]
        assert len_in_bytes == len(d.value_bytes)
        tile_size = 6  # 6 bytes per tile as defined in CCP for DNLOAD_6
        tiles = len_in_bytes // tile_size 
        last_tile = len_in_bytes % tile_size
        # Download full size tiles with DNLOAD_6
        for i in range(tiles):
            ctr += 1
            cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/DNLOAD_6(data=d.value_bytes[i*tile_size:(i+1)*tile_size])
            dto = sock.sr1(cro,timeout=timeout)
            assert dto.return_code == 0x00
        start_index = tiles * tile_size
        ctr += 1 
        cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/DNLOAD(data=d.value_bytes[start_index:start_index+last_tile])
        dto = sock.sr1(cro,timeout=timeout)
        assert dto.return_code == 0x00

    # DISCONNECT
    ctr += 1
    cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/DISCONNECT(station_address=0x00)
    dto = sock.sr1(cro,timeout=timeout)
    assert dto.return_code == 0x00

# %% ../nbs/02.ccp.ipynb 82
def upload_calib_data(xcp_calib: XCPCalib, 
                        can_type: CANType, 
                        channel: int,
                        bus_type: BusType, 
                        can_filter=list[dict],  
                        bit_rate: int=500_000, 
                        timeout: float=1.0,
                        diff_flashing: bool=False)->None:
    """Summary
    Upload XCP calibration data from target to host, the result will update the xcp_calib.data field

    Args:
        xcp_calib (XCPCalib): XCP calibration  to be uploaded from the target to host
        diff_flashing (bool): Use differential flashing
    """

    # init counter
    ctr = 0
    # create a socket
    match can_type:
        case 'NATIVE':
            load_layer("can")
            conf.contribs['CANSocket'] = {'use-python-can': False}
            load_contrib("cansocket")
            match bus_type:
                case 'SOCKET':
                    sock = CANSocket(channel='can'+str(channel), can_filter=can_filter, bit_rate = bit_rate, receive_own_messages=True)
                case 'VIRTUAL':
                    sock = CANSocket(channel='vcan'+str(channel), can_filter=can_filter, bit_rate = bit_rate, receive_own_messages=True)
                case _:
                    raise ValueError(f"Invalid CAN bus type: {bus_type}, valid types are: SOCKET or VIRTUAL for Native CANSOCKET")
        case 'PYTHON': 
            assert bus_type is not None, "Bus type must be specified for PYTHON CAN"
            load_layer("can")
            conf.contribs['CANSocket'] = {'use-python-can': True}
            load_contrib("cansocket")
            match bus_type:
                case 'SOCKET':
                    sock = CANSocket(bustype='socketcan', channel='can'+channel, can_filter=can_filter, bitrate=bit_rate, receive_own_messages=True)
                case 'VIRTUAL':
                    sock = CANSocket(bustype='socketcan', channel='vcan'+channel, can_filter=can_filter, bitrate=bit_rate, receive_own_messages=True)
                case 'KVASER':
                    sock = CANSocket(bustype='kvaser', channel=channel, can_filter=can_filter, bitrate=bit_rate, receive_own_messages=True)
                case 'VECTOR':
                    sock = CANSocket(bustype='vector', channel=channel, can_filter=can_filter, bitrate=bit_rate, receive_own_messages=True)
                case _:
                    raise ValueError(f"Invalid CAN bus type: {bus_type}, implemented valid types are: SOCKET, KVASER, VECTOR for Python-CAN CANSOCKET")
    # sock = CANSocket(channel='can'+str(xcp_calib.config.channel), receive_own_messages=True)

    # CONNECT
    ctr += 1
    cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/CONNECT(station_address=0x00)
    dto = sock.sr1(cro,timeout=timeout)
    assert dto.return_code == 0x00

    for d in xcp_calib.data:
        # SET_MTA
        ctr += 1
        cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/SET_MTA(address=int(d.address, 16))
        dto = sock.sr1(cro,timeout=timeout)
        assert dto.return_code == 0x00

        # Determine message tiling
        len_in_bytes = d.type_size * d.dim[0] * d.dim[1]
        # assert len_in_bytes == len(d.value_bytes)
        tile_size = 5
        tiles = len_in_bytes // tile_size 
        last_tile = len_in_bytes % tile_size
        
        # Upload tiles with tile_size (maximal 5 as defined by CCP） bytes with UPLOAD
        ba_uploaded = bytearray()
        for i in range(tiles):
            ctr += 1
            cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/UPLOAD(size=tile_size)
            upload_dto = sock.sr1(cro,timeout=timeout)
            assert upload_dto.return_code == 0x00
            ba_uploaded += upload_dto.data
            

        start_index = tiles * tile_size
        ctr += 1 
        cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/UPLOAD(last_tile)
        upload_dto = sock.sr1(cro,timeout=timeout)
        assert upload_dto.return_code == 0x00
        ba_uploaded += upload_dto.data

        d.value = ba_uploaded.hex()

    # DISCONNECT
    ctr += 1
    cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/DISCONNECT(station_address=0x00)
    dto = sock.sr1(cro,timeout=timeout)
    assert dto.return_code == 0x00

# %% ../nbs/02.ccp.ipynb 83
@contextlib.contextmanager
def scapy_can_context(can_specs: ScapyCANSpecs):
    """Summary
    Context manager for scapy CAN socket

    Args:
        can_specs (ScapyCANSpecs): CAN specs including can type, bus type, channel, etc.

    Yields:
        CANSocket: CAN socket object
    """
    # create a socket
    try:
        match can_specs.can_type:
            case 'NATIVE':
                load_layer("can")
                conf.contribs['CANSocket'] = {'use-python-can': False}
                load_contrib("cansocket")
                sock = CANSocket(channel=can_specs.channel, 
                                    can_filter=can_specs.can_filters, 
                                    bit_rate = can_specs.bit_rate, 
                                    receive_own_messages=can_specs.receive_own_messages
                                )
            case 'PYTHON': 
                load_layer("can")
                conf.contribs['CANSocket'] = {'use-python-can': True}
                load_contrib("cansocket")
                match bus_type:
                    case 'SOCKET' | 'VIRTUAL':
                        sock = CANSocket(bustype='socketcan', 
                                            channel=can_specs.channel, 
                                            can_filter=can_specs.can_filters, 
                                            bitrate=can_specs.bit_rate, 
                                            receive_own_messages=can_specs.receive_own_messages
                                        )
                    case 'KVASER' | 'VECTOR':
                        sock = CANSocket(bustype=can_specs.bus_type.lower(), 
                                            channel=can_specs.channel, 
                                            can_filter=can_specs.can_filters, 
                                            bitrate=can_specs.bit_rate, 
                                            receive_own_messages=can_specs.receive_own_messages)
                    case _:
                        raise ValueError(f"Invalid CAN bus type: {can_specs.bus_type}, implemented valid types are: SOCKET, VIRTUAL, KVASER, VECTOR")
    except Exception as e:
        raise Exception(f"Failed to create CAN socket: {e}")

    # CONNECT
    can_specs.cntr += 1
    cro = CCP(identifier=can_specs.can_id)/CRO(ctr=can_specs.cntr)/CONNECT(station_address=can_specs.station_address)
    dto = sock.sr1(cro, timeout=can_specs.time_out)
    assert dto is not None, f"Failed to connect to target, timeout={can_specs.time_out} seconds"
    assert dto.return_code == 0x00
    
    try: 
        yield sock
    except TimeoutError:
        raise TimeoutError(f"CAN socket timeout: {can_specs.time_out} seconds")
    except Exception as e:
        raise e
    finally:
        # DISCONNECT
        can_specs.cntr += 1
        cro = CCP(identifier=can_specs.can_id)/CRO(ctr=can_specs.cntr)/DISCONNECT(station_address=can_specs.station_address)
        dto = sock.sr1(cro, timeout=can_specs.time_out)
        assert dto.return_code == 0x00

# %% ../nbs/02.ccp.ipynb 84
@contextlib.contextmanager
def scapy_SET_MTA_context(can_specs: ScapyCANSpecs, sock: CANSocket, data: XCPData) -> CAN:
    """Summary
    Context manager for scapy set_mta 

    Args:
        channel (str): CAN channel to use, default is vcan0

    Yields:
        CAN: packdet for CAN message 
    """

    # SET_MTA 
    can_specs.cntr += 1
    cro = CCP(identifier=can_specs.can_id)/CRO(ctr=can_specs.cntr)/SET_MTA(address=int(data.address, 16))
    dto = sock.sr1(cro, timeout=can_specs.time_out)
    assert dto.return_code == 0x00
    try:
        yield dto
    except TimeoutError:
        raise TimeoutError(f"CAN socket timeout: {can_specs.time_out} seconds")
    except Exception as e:
        raise e
    finally:
        pass  # do nothing, just pray it'll be OK. Crapy CCP!
    


# %% ../nbs/02.ccp.ipynb 85
@contextlib.contextmanager
def scapy_load_context(can_specs: ScapyCANSpecs, sock: CANSocket, data: XCPData, start_index: int, tile_size: int):
    """Summary
    Context manager for scapy load (download or upload)

    Args:
        channel (str): CAN channel to use, default is vcan0

    Yields:
        CANSocket: CAN socket object
    """

    can_specs.cntr += 1
    if can_specs.download_upload:
        assert tile_size <=6 and tile_size >0, f"In CCP Tile size must be non-zero and less than 6 bytes, got: {tile_size}"
        if tile_size == 6:
            # cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/DNLOAD_6(data=d.value_bytes[i*tile_size:(i+1)*tile_size])
            cro = CCP(identifier=can_specs.can_id)/CRO(ctr=can_specs.cntr)/DNLOAD_6(data=d.value_bytes[start_index:start_index+tile_size])
            dto = sock.sr1(cro,timeout=can_specs.time_out)
            assert dto.return_code == 0x00
        else: 
            # start_index = tiles * tile_size
            # cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/DNLOAD(data=d.value_bytes[start_index:start_index+last_tile])
            cro = CCP(identifier=can_specs.can_id)/CRO(ctr=can_specs.cntr)/DNLOAD(data=d.value_bytes[start_index:start_index+tile_size])
            dto = sock.sr1(cro,timeout=can_specs.time_out)
            assert dto.return_code == 0x00
    else:  # False if in upload mode
        assert tile_size <=5 and tile_size >0, f"In CCP Tile size must be non-zero and less than 5 bytes for Uploading, got: {tile_size}"
        # cro = CCP(identifier=xcp_calib.config.download_can_id)/CRO(ctr=ctr)/DNLOAD_6(data=d.value_bytes[i*tile_size:(i+1)*tile_size])
        cro = CCP(identifier=can_specs.can_id)/CRO(ctr=can_specs.cntr)/UPLOAD(size=tile_size)  #start_index or data not used for uploading. target ECU will increment the address!
        dto = sock.sr1(cro,timeout=can_specs.time_out)
        assert dto.return_code == 0x00
    try: 
        yield dto
    except TimeoutError:
        raise TimeoutError(f"CAN socket timeout: {timeout} seconds")
    except Exception as e:
        raise e
    finally:
        pass  # do nothing, just pray it'll be OK. Crapy CCP!

# %% ../nbs/02.ccp.ipynb 87
def downlod_calib_data2(xcp_calib: XCPCalib, 
                        can_type: str='NATIVE', 
                        bus_type: str='VIRTUAL', 
                        bit_rate: int=500_000, 
                        timeout: float=1.0,
                        station_address: int = 0x00,
                        diff_flashing: bool=False):
    """Summary
    Download XCP calibration data to target use scapy_can_context

    Args:
        xcp_calib (XCPCalib): XCP calibration  to be downloaded into the target
        diff_flashing (bool): Use differential flashing
    """
    # init counter
    cntr = 0

    can_filters = [{'can_id': xcp_calib.config.upload_can_id, 'can_mask': 0x7FF}]
    can_specs = ScapyCANSpecs(can_type=can_type,
                            bus_type=bus_type,
                            channel_serial_number=xcp_calib.config.channel,
                            can_id=xcp_calib.config.download_can_id,
                            can_filters=can_filters,
                            bit_rate=bit_rate,
                            time_out=timeout,
                            station_address=station_address,
                            cntr=cntr,
                            download_upload=True,  # CCP Download mode
                            receive_own_messages=True
                            )
    try:
        with scapy_can_context(can_specs=can_specs) as sock:
            for d in xcp_calib.data:
                # SET_MTA
                with scapy_SET_MTA_context(can_specs=can_specs, sock=sock, data=d) as dto:
                    assert dto.return_code==0x00, f"SET_MTA failed for {d.name} at {d.address}"
                    # Determine message tiling
                    len_in_bytes = d.type_size * d.dim[0] * d.dim[1]
                    assert len_in_bytes == len(d.value_bytes)
                    tile_size = 6  # 6 bytes per tile as defined in CCP for DNLOAD_6
                    tiles = len_in_bytes // tile_size 
                    last_tile = len_in_bytes % tile_size
                    # Download full size tiles with DNLOAD_6
                    for i in range(tiles):
                        start_index = i*tile_size
                        with scapy_load_context(can_specs=can_specs, sock=sock, data=d, start_index=start_index, tile_size=tile_size) as dto:
                            assert dto.return_code == 0x00, f"DNLOAD_6 failed at tile: {i}"

                    start_index = tiles * tile_size
                    with scapy_load_context(can_specs=can_specs, sock=sock, data=d, start_index=start_index, tile_size=last_tile) as dto:
                        assert dto.return_code == 0x00, f"DNLOAD failed at last tile: {i} of size {last_tile}"
    except Exception as e:
        print(e)

# %% ../nbs/02.ccp.ipynb 90
def upload_calib_data2(xcp_calib: XCPCalib, 
                        can_type: str='NATIVE', 
                        bus_type: str='VIRTUAL', 
                        bit_rate: int=500_000, 
                        timeout: float=1.0,
                        station_address: int = 0x00,
                        diff_flashing: bool=False):

    """Summary
    Upload XCP calibration data from target to host, the result will update the xcp_calib.data field

    Args:
        xcp_calib (XCPCalib): XCP calibration  to be uploaded from the target to host
        diff_flashing (bool): Use differential flashing
    """

    # init counter
    cntr = 0

    can_filters = [{'can_id': xcp_calib.config.upload_can_id, 'can_mask': 0x7FF}]
    can_specs = ScapyCANSpecs(can_type=can_type,
                            bus_type=bus_type,
                            channel_serial_number=xcp_calib.config.channel,
                            can_id=xcp_calib.config.download_can_id,
                            can_filters=can_filters,
                            bit_rate=bit_rate,
                            time_out=timeout,
                            station_address=station_address,
                            cntr=cntr,
                            receive_own_messages=True,
                            download_upload=False  # CCP Upload mode
                            )
    with scapy_can_context(can_specs=can_specs) as sock:
        for d in xcp_calib.data:
            # SET_MTA
            with scapy_SET_MTA_context(can_specs=can_specs, sock=sock, data=d) as dto:
                assert dto.return_code==0x00, f"SET_MTA failed for {d.name} at {d.address}"

                # Determine message tiling
                len_in_bytes = d.type_size * d.dim[0] * d.dim[1]
                # assert len_in_bytes == len(d.value_bytes)
                tile_size = 5
                tiles = len_in_bytes // tile_size 
                last_tile = len_in_bytes % tile_size

                # Upload tiles with tile_size (maximal 5 as defined by CCP） bytes with UPLOAD
                ba_uploaded = bytearray()
                for i in range(tiles):
                    with scapy_load_context(can_specs=can_specs, sock=sock, data=d, start_index=i*tile_size, tile_size=tile_size) as upload_dto:
                        assert upload_dto.return_code == 0x00, f"UPLOAD failed at tile: {i}"
                        ba_uploaded += upload_dto.data


                with scapy_load_context(can_specs=can_specs, sock=sock, data=d, start_index=i*tile_size, tile_size=last_tile) as upload_dto:
                    assert upload_dto.return_code == 0x00, f"UPLOAD failed at tile: {i}"
                    ba_uploaded += upload_dto.data
                    ba_uploaded += upload_dto.data

                d.value = ba_uploaded.hex()


# %% ../nbs/02.ccp.ipynb 95
if __name__ == "__main__" and "__file__" in globals():  # only run if this file is called directly

    protocol = inquirer.select(
        message="What's the protocol?",
        choices=[
            Choice(value="ccp", name="CCP"),
            Choice(value="xcp", name="XCP"),
        ],
        default="ccp",
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
        default=False,
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

    can_channel = inquirer.number(
        message="CAN channel for flashing",
        min_allowed=0,
        max_allowed=32,
        validate=EmptyInputValidator(),
        default=3,
    ).execute()

    download_id = inquirer.number(
        message="CAN ID for downloading",
        min_allowed=0,
        max_allowed=9999,
        validate=EmptyInputValidator(),
        default=630,
    ).execute()

    upload_id = inquirer.number(
        message="CAN ID for uploading",
        min_allowed=0,
        max_allowed=9999,
        validate=EmptyInputValidator(),
        default=631,
    ).execute()

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
    args.download = download
    args.diff_flashing = differential_flashing
    # args.a2l = a2l_file_path
    # args.node_path = node_path
    # args.leaves = leaves
    args.channel = can_channel
    args.download_id = download_id
    args.upload_id = upload_id
    args.input = repo.working_dir+input_file_path
    args.output = repo.working_dir+output_file_path
    pprint(args)

    xcp_calib_from_xcpjson = Get_XCPCalib_From_XCPJSon(args.input)
    xcp_data = Generate_Init_XCPData_From_A2L(
        a2l=args.a2l, keys=args.leaves, node_path=args.node_path
    )
    try:
        XCPData.model_validate(xcp_data)
    except ValidationError as exc:
        print(exc)

    xcp_data.value = xcp_calib_from_xcpjson.data[0].value
    pprint(xcp_data)

    xcp_calib = XCPCalib(
        config=XCPConfig(
            channel=args.channel, download=args.download_id, upload=args.upload_id
        ),
        data=[xcp_data],
    )
    pprint(xcp_calib)
