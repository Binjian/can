# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/02.xcp.ipynb.

# %% auto 0
__all__ = ['get_argparser']

# %% ../nbs/02.xcp.ipynb 3
import argparse
from InquirerPy import inquirer
from InquirerPy.validator import EmptyInputValidator
from InquirerPy.base.control import Choice

# %% ../nbs/02.xcp.ipynb 4
def get_argparser() -> argparse.ArgumentParser:
	"""Summary
	Get argument parser for command line arguments

	Returns:
		argparse.ArgumentParser: _description_
	"""
	parser = argparse.ArgumentParser(description='XCP Processing')

	parser.add_argument(
		'-p',
		'--protocol',
		type=str,
		choices=['ccp', 'xcp'],
		default='ccp',
		help='Protocol to use: ccp/xcp',
	)

	parser.add_argument(
		'-u',
		'--upload',
		default=False,
		help='Download or upload: default is download(host->target)',
		action='store_false',
	)

	parser.add_argument(
		'-d',
		'--diff_flashing',
		type=True,
		help='use differential flashing',
		action='store_true',
	)

	parser.add_argument(
		'-i', 
		'--input', 
		type=str, 
		help='Input file path')
	
	parser.add_argument(
		'-o'
		'--output', 
		type=str, 
		help='Output file path')
	return parser

# %% ../nbs/02.xcp.ipynb 6
if __name__ == '__main__' and "__file__" in globals():  # only run if this file is called directly 

    protocol = inquirer.select(
        message="What's the protocol?",
        choices=[
            Choice(value="ccp", name="CCP"),
            Choice(value="xcp", name="XCP"),
        ],
        default="ccp",
    ).execute()    

    upload = inquirer.confirm(
        message="Uploading(target->host)?",
        confirm_letter="y",
        reject_letter="n",
        default=False,
    ).execute()

    differential_flash = inquirer.confirm(
        message="Differential Flashing?",
        default=False,
        confirm_letter="y",
        reject_letter="n",
    ).execute()

    input_file_path = inquirer.text(
        message="Input file path",
        validate=EmptyInputValidator(),
		default="../res/download.json",
    ).execute()

    output_file_path = inquirer.text(
        message="Output file path",
        validate=EmptyInputValidator(),
		default="../res/output.json",
    ).execute()
    
        
    args = get_argparser().parse_args()
    args.protocol = protocol
    args.upload = upload
    args.diff_flashing = differential_flash
    args.input = input_file_path
    args.output = output_file_path

    print(args)
    
