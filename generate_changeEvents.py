# This script generates a networkChangeEvents xml file
# Inputs - flood_network CSV outputs

import re
import pandas as pd
from datetime import datetime, timedelta
import json
from pathlib import Path

def load_config(filepath):
    with open(filepath, 'r') as file:
        return json.load(file)


def write_headers(file):
    file.write(f'<?xml version="1.0" encoding="UTF-8"?>\n')
    file.write(
        f'<networkChangeEvents xmlns="http://www.matsim.org/files/dtd" '
        f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        f'xsi:schemaLocation="http://www.matsim.org/files/dtd '
        f'http://www.matsim.org/files/dtd/networkChangeEvents.xsd">\n\n'
    )


def load_df(filepath, config):
    df = pd.read_csv(filepath)
    df = df.drop_duplicates(config["id_column"])
    df = df[df[config["id_column"]].notna()]
    return df


def calculate_time(time1, time2, time_format):
    t1 = datetime.strptime(time1, time_format)
    t2 = datetime.strptime(time2, time_format)

    delta1 = timedelta(hours=t1.hour, minutes=t1.minute, seconds=t1.second)
    delta2 = timedelta(hours=t2.hour, minutes=t2.minute, seconds=t2.second)

    total_delta = delta1 + delta2

    total_seconds = int(total_delta.total_seconds())
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    return f"{hours:02}:{minutes:02}:{seconds:02}"


# TODO: Update input and output naming based on citycat outputs
def sort_filenames(files):
    return sorted(files, key=lambda x: int(re.search(r'_T(\d+)_', x).group(1)))


def main(config_filepath, flood_network_csv_filepath, output_dir):
    config_filepath = Path(config_filepath)
    flood_network_csv_filepath = Path(flood_network_csv_filepath)
    output_dir = Path(output_dir)

    config = load_config(config_filepath)["generate_changeEvents"]

    with open(output_dir / "networkChangeEvents.xml", "w") as writefile:
        write_headers(writefile)
        current_time = config["event_start_time"]

        dataframe = load_df(flood_network_csv_filepath, config)
        velocity_cols = [col for col in dataframe.columns if col.endswith("_" + config["velocity_column"])]

        if len(velocity_cols) != 1:
            velocity_cols = sort_filenames(velocity_cols)

        for column in velocity_cols:
            print(column)
            grouped = dataframe.groupby(column)
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

            current_time = calculate_time(
                current_time,
                config["time_interval"],
                config["time_format"])

        writefile.write(f'</networkChangeEvents>\n')

    print('Done')


if __name__ == "__main__":
    main(
        config_filepath="",
        flood_network_csv_filepath="",
        output_dir=""
    )