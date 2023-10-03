import argparse
import psycopg2

BANDS_TO_IMPORT = ['wld_map']

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(help="Type of Download")
    parser.add_argument("-s", "--save", required=True)

    args = parser.parse_args()

    downloaded_data_dir = args.save

