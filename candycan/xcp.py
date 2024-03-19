# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02.xcp.ipynb.

# %% auto 0
__all__ = ['pp', 'repo', 'get_argparser', 'npa_to_packed_buffer', 'flash_xcp']

# %% ../nbs/02.xcp.ipynb 3
import os
import git
import argparse
from InquirerPy import inquirer
from InquirerPy.validator import EmptyInputValidator
from InquirerPy.base.control import Choice
from pydantic import ValidationError
from pprint import pprint, PrettyPrinter

# %% ../nbs/02.xcp.ipynb 4
import subprocess
from multiprocessing import Manager
from multiprocessing.managers import DictProxy
import cantools
from cantools.database import Message as MessagerTpl
from cantools.database.can.database import Database

# %% ../nbs/02.xcp.ipynb 5
import pandas as pd
import numpy as np
import struct

# %% ../nbs/02.xcp.ipynb 7
from candycan.a2l import (
    list_of_strings,
    XCPCalib,
    XCPData,
    XCPConfig,
    Get_XCPCalib_From_XCPJSon,
    Generate_Init_XCPData_From_A2L,
)


# %% ../nbs/02.xcp.ipynb 8
pp = PrettyPrinter(indent=4, width=80, compact=True)

# %% ../nbs/02.xcp.ipynb 9
repo = git.Repo("./", search_parent_directories=True)  # get the Repo object of tspace
if os.path.basename(repo.working_dir) != "candycan":  # I'm in the parent repo!
    repo = repo.submodule("candycan").module()
pprint(repo.working_dir)

# %% ../nbs/02.xcp.ipynb 10
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

# %% ../nbs/02.xcp.ipynb 21
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

# %% ../nbs/02.xcp.ipynb 24
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
        

    

# %% ../nbs/02.xcp.ipynb 25
from scapy.all import *

# %% ../nbs/02.xcp.ipynb 46
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
