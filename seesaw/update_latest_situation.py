"""Usage:
    update_latest_situation.py <rule>
    update_latest_situation.py -h | --help

Options:
    -h --help                Show this screen and exit.
"""

from docopt import docopt
import os
import glob
import csv
import re
from datetime import datetime

def init(filepath):
    dir = os.path.dirname(filepath)
    if not os.path.exists(dir):
        os.makedirs(dir)

def generate_latest(txt, input_tsv_filepath):
    input_files = glob.glob(input_tsv_filepath, recursive = True)
    input_files.sort(reverse = True)
    for f in input_files:
        lenght = len(open(f).readlines())
        tsv = csv.reader(open(f, "r"), delimiter = '\t')
        i = 0
        for row in tsv:
            if i >= lenght - 10:
                txt.write("\t".join(row) + "\n")
            i += 1
        break

def get_max_line(input_tsv_filepath, f, hors):
    now = datetime.now()
    input_files = glob.glob(input_tsv_filepath, recursive = True)
    input_files.sort()
    max = None
    max_line = ""
    repatter = re.compile(r'[0-9]{4}-[0-9]{2}-[0-9]{2}')
    for path in input_files:
        filetime = repatter.search(path)  # Extract date from filepath
        if filetime:
            ft = datetime.strptime(filetime.group(0) + " 23:59:59", "%Y-%m-%d %H:%M:%S")
            if (now - ft).total_seconds() < hors * 60 * 60:
                print(filetime)
                tsv = csv.reader(open(path, "r"), delimiter = '\t')
                for row in tsv:
                    if max is None:
                        max = f(row)
                        max_line = "\t".join(row)
                    elif max < f(row):
                        max = f(row)
                        max_line = "\t".join(row)
    return max_line

if __name__ == '__main__':
    args = docopt(__doc__)
    rule = args["<rule>"]

    output_filepath = "./seesaw/tmp/%s.txt" % rule
    init(output_filepath)

    input_tsv_filepath = "./log/seesaw/monitor/%s*" % rule

    with open(output_filepath, 'w') as txt:
        txt.write("=== latest ===\n")
        generate_latest(txt, input_tsv_filepath)
        txt.write("\n")

        txt.write("=== exchange1 MAX ===\n")
        txt.write("1day : " + get_max_line(input_tsv_filepath, lambda row: float(row[1]), 24) + "\n")
        txt.write("3days: " + get_max_line(input_tsv_filepath, lambda row: float(row[1]), 24 * 3) + "\n")
        txt.write("7days: " + get_max_line(input_tsv_filepath, lambda row: float(row[1]), 24 * 7) + "\n")
        txt.write("\n")

        txt.write("=== exchange2 MAX ===\n")
        txt.write("1day : " + get_max_line(input_tsv_filepath, lambda row: float(row[2]), 24) + "\n")
        txt.write("3days: " + get_max_line(input_tsv_filepath, lambda row: float(row[2]), 24 * 3) + "\n")
        txt.write("7days: " + get_max_line(input_tsv_filepath, lambda row: float(row[2]), 24 * 7) + "\n")
        txt.write("\n")
