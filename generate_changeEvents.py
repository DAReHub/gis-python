# This script generates a networkChangeEvents xml file
# Inputs - flood_network CSV outputs

import os
import re
import pandas as pd
from datetime import datetime, timedelta
import json


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
    df = df[[config["id_column"], config["velocity_column"]]]
    df = df.drop_duplicates(config["id_column"])
    df = df[df[config["id_column"]].notna()]
    df = df[df[config["velocity_column"]].notna()] # TODO: Make sure there are no nan values coming from flooded_network
    df.sort_values(by=config["velocity_column"], inplace=True, ascending=True)
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


def main(config_filepath, input_dir, output_dir):
    config = load_config(config_filepath)["generate_changeEvents"]

    with open(output_dir + "networkChangeEvents.xml", "w") as writefile:
        write_headers(writefile)
        current_time = config["event_start_time"]

        files = os.listdir(input_dir)
        files = [i for i in files if ".csv" in i]
        files = sort_filenames(files)

        for filename in files:
            print(filename)
            filepath = input_dir + filename
            df = load_df(filepath, config)
            grouped = df.groupby(config["velocity_column"])
            dfs = {value: df for value, df in grouped}

            for value, df in dfs.items():
                writefile.write(f'<networkChangeEvent startTime="{current_time}">\n')
                links = df["ID"].to_list()
                for link in links:
                    writefile.write(f'<link refId="{link}"/>\n')
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
        input_dir="",
        output_dir=""
    )