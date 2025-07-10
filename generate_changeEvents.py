# This script generates a networkChangeEvents xml file
# Inputs - flood_network CSV outputs

import re
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import argparse

def write_headers(file):
    file.write(f'<?xml version="1.0" encoding="UTF-8"?>\n')
    file.write(
        f'<networkChangeEvents xmlns="http://www.matsim.org/files/dtd" '
        f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        f'xsi:schemaLocation="http://www.matsim.org/files/dtd '
        f'http://www.matsim.org/files/dtd/networkChangeEvents.xsd">\n\n'
    )


def load_df(filepath, id):
    df = pd.read_csv(filepath)
    df = df.drop_duplicates(id)
    return df[df[id].notna()]


def calculate_time(time1, time2, time_format="%H:%M:%S"):
    t1 = datetime.strptime(time1, time_format)
    t2 = datetime.strptime(time2, time_format)

    delta1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
    delta2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)

    total_delta = delta1 + delta2

    total_seconds = int(total_delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"{hours:02}:{minutes:02}:{seconds:02}"


# Sorts based on T value, e.g. R1_C1_T0_0min, R1_C1_T1_5min, ...
def sort_filenames(files):
    return sorted(files, key=lambda x: int(re.search(r'_T(\d+)_', x).group(1)))


def main(
    flood_network_csv_filepath: str,
    output_dir: str,
    event_start_time: str,
    time_interval: str,
    flood_network_id_name: str,
    velocity_keyword: str
):

    flood_network_csv_filepath = Path(flood_network_csv_filepath)
    output_dir = Path(output_dir)

    df = load_df(flood_network_csv_filepath, flood_network_id_name)
    velocity_cols = [
        col for col in df.columns if col.endswith("_" + velocity_keyword)
    ]

    if len(velocity_cols) == 0:
        raise Exception(f"No fields found containing velocity_keyword: {velocity_keyword}")

    if len(velocity_cols) > 1:
        velocity_cols = sort_filenames(velocity_cols)

    with open(output_dir / "networkChangeEvents.xml", "w") as writefile:
        write_headers(writefile)
        current_time = event_start_time

        for column in velocity_cols:
            print(column)
            grouped = df.groupby(column)
            dfs = {value: df for value, df in grouped}

            for value, data in dfs.items():
                writefile.write(f'<networkChangeEvent startTime="{current_time}">\n')
                links = data["ID"].to_list()
                for link in links:
                    writefile.write(f'<link refId="{link}"/>\n')

                # MATSim doesn't accept 0 speed - use very small alternative
                if value == 0:
                    value = 0.001

                writefile.write(f'<freespeed type="absolute" value="{value}"/>\n')
                writefile.write("</networkChangeEvent>\n")

            # TODO: Calculate time interval automatically from column names
            current_time = calculate_time(current_time, time_interval)

        writefile.write(f'</networkChangeEvents>\n')

    print('Done')


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        '--flood_network_csv_filepath',
        required=True,
        type=str
    )
    p.add_argument(
        '--output_dir',
        required=False,
        default=".",
        type=str,
        help='(optional) Default=.'
    )
    p.add_argument(
        '--event_start_time',
        required=True,
        type=str,
        help="Event start time as format %%H:%%M:%%S (e.g. 12:00:00 for 12pm)"
    )
    p.add_argument(
        '--time_interval',
        required=True,
        type=str,
        help="Interval time as format %%H:%%M:%%S (e.g. 00:10:00 for a 10 min interval)"
    )
    p.add_argument(
        '--flood_network_id_name',
        required=False,
        default="ID",
        help='(optional) Default=ID Name of the network ID field',
        type=str,
    )
    p.add_argument(
        '--velocity_keyword',
        required=False,
        default="velocity",
        type=str,
        help='(optional) Default=velocity'
    )
    args = p.parse_args()

    main(
        flood_network_csv_filepath=args.flood_network_csv_filepath,
        output_dir=args.output_dir,
        event_start_time=args.event_start_time,
        time_interval=args.time_interval,
        flood_network_id_name=args.flood_network_id_name,
        velocity_keyword=args.velocity_keyword
    )