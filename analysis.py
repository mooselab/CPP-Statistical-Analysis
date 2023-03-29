import json
import re
import sys
import subprocess
from pathlib import Path
import xml.etree.ElementTree as ET
import lizard

from utils import get_element_texts

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 analysis.py <input_directory>")
        exit(1)

    input_directory = sys.argv[1]
    if not Path(input_directory).is_dir():
        print("Input directory does not exist")
        exit(1)

    io_operations = ['fopen', 'freopen', 'fclose', 'fflush', 'fwide', 'setbuf', 'setvbuf',
                     'fread', 'fwrite',
                     'getc', 'fgetc', 'fgets', 'putc', 'fputc', 'fputs', 'getchar', 'gets', 'putchar', 'puts', 'ungetc',
                     'fgetwc', 'getwc', 'fgetws', 'fputwc', 'putwc', 'fputws', 'ungetwc', 'getwchar', 'putwchar',
                     'scanf', 'fscanf', 'sscanf', 'printf', 'fprintf', 'sprintf', 'snprintf', 'vprintf', 'vfprintf', 'vsprintf', 'vsnprintf','vscanf', 'vfscanf', 'vsscanf',
                     'wscanf', 'fwscanf', 'swscanf', 'wprintf', 'fwprintf', 'swprintf', 'vfwprintf', 'vswprintf', 'vwprintf', 'vwscanf', 'vfwscanf', 'vswscanf',
                     'ftell', 'fseek', 'rewind', 'fgetpos', 'fsetpos', 
                     'clearerr', 'feof', 'ferror', 'perror',
                     'remove', 'rename', 'tmpfile', 'tmpnam', 'tmpnam_r']

    result = []
    callers = {}
    mpi_functions = []

    # Loop through all files in the input directory
    for ext in ['*.cpp', '*.cxx', '*.cc', '*.c']:
        for p in Path(input_directory).rglob(ext):
            process = subprocess.run(['srcml', p], capture_output=True) # Run srcml on file
            xml = process.stdout.decode('utf-8')
            xml = re.sub('xmlns="[^"]+"', '', xml, count=1) # Remove namespace

            root = ET.fromstring(xml)

            complexities = {f.__dict__['long_name'].split('(')[0]: f.__dict__['cyclomatic_complexity'] for f in lizard.analyze_file(str(p)).function_list}

            # Get root functions
            for function in root.findall('function'):
                # Find all loops and nested loops
                loops = []
                loops.extend(function.findall('.//for') + function.findall('.//while') + function.findall('.//do'))

                # function_name = get_element_texts(function.find('name')) + get_element_texts(function.find('parameter_list'))
                function_name = get_element_texts(function.find('name'))

                # Find the number of semi-colons in the function
                number_of_semicolons = ''.join(function.itertext()).count(';')

                number_of_nested_loops = 0
                for loop in loops:
                    nested_loops = []
                    nested_loops.extend(loop.findall('.//for') + loop.findall('.//while') + loop.findall('.//do'))
                    number_of_nested_loops += len(nested_loops)

                    if loop.find('control') is not None:
                        number_of_semicolons -= ''.join(loop.find('control').itertext()).count(';')

                number_of_loops = len(loops)

                # Check if function has I/O operations
                has_io = any(get_element_texts(call.find('name')) in io_operations for call in function.findall('.//call'))

                # Find number of blocks
                number_of_blocks = len(function.findall('.//block'))

                # Add functions callees
                # Check if function is recursive
                # Add the function call to the callers dictionary
                callees = []
                is_recursive = False
                is_MPI = False
                for call in function.findall('.//call'):
                    callee_name = get_element_texts(call.find('name'))
                    callees.append(callee_name) 
                    
                    if callee_name == function_name.split(')')[0]:
                        is_recursive = True

                    if callee_name.startswith('MPI_'):
                        is_MPI = True
                        mpi_functions.append(function_name)

                    if callee_name not in callers:
                        callers[callee_name] = 0
                    callers[callee_name] += 1

                # Number of statements individually
                number_of_expression_statements = len(function.findall('.//expr_stmt'))
                number_of_declaration_statements = len(function.findall('.//decl_stmt'))
                number_of_empty_statements = len(function.findall('.//empty_stmt'))

                # Number of branches
                number_of_if = len(function.findall('.//if') + function.findall('.//else'))
                number_of_switch = len(function.findall('.//switch'))
                number_of_preprocessor_if = len(function.findall('.//{http://www.srcML.org/srcML/cpp}if') + function.findall('.//{http://www.srcML.org/srcML/cpp}else') + function.findall('.//{http://www.srcML.org/srcML/cpp}elif'))

                # Check if file is already in result
                if not any(x.get('file', '&') == str(p).replace(input_directory + '/', '') for x in result):
                    result.append({
                        'file': str(p).replace(input_directory + '/', ''),
                        'functions': []
                    })

                for item in result:
                    if item['file'] == str(p).replace(input_directory + '/', ''):
                        item['functions'].append({
                            'name': function_name,
                            'line_of_codes': number_of_semicolons + number_of_blocks - 1, # -1 because of the function entire block
                            'has_io': has_io,
                            'is_MPI': is_MPI,
                            'cyclomatic_complexity': complexities.get(function_name, 0),
                            'number_of_loops': number_of_loops,
                            'number_of_nested_loops': number_of_nested_loops,
                            'number_of_calls': callees,
                            'is_recursive': is_recursive,
                            'number_of_statements': {
                                'number_of_expression_statements': number_of_expression_statements,
                                'number_of_declaration_statements': number_of_declaration_statements,
                                'number_of_empty_statements': number_of_empty_statements
                            },
                            'number_of_branches': {
                                'number_of_if': number_of_if,
                                'number_of_switch': number_of_switch,
                                'number_of_preprocessor_if': number_of_preprocessor_if
                            }
                        })

    # Add the number of callers to the result
    # Check if function is calling MPI functions
    for item in result:
        for function in item['functions']:
            function['number_of_callers'] = callers.get(function['name'], 0)

            # Check if function is calling MPI functions
            function['is_calling_MPI'] = any(x in mpi_functions for x in function['number_of_calls'])

            # Set number of calls (replace list with number)
            function['number_of_calls'] = len(function['number_of_calls'])

    # Write result to file
    with open('result.json', 'w') as f:
        json.dump(result, f, indent=4)