import os
import sys
from translate import *
def main():

    assert len(sys.argv) > 1, "input file path is required"

    input_path = sys.argv[1]
    assert os.path.exists(input_path), "file not found"

    with open(input_path, "r") as input:
        output_lines = [SQLStatement().GetSQL(x) for x in input.readlines()]

    with open("out.txt", "w") as output:
        output.write("\n".join(output_lines))
    print("Result SQL queries in out.txt")

if __name__ == "__main__":
    main()
