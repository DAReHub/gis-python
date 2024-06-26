# This script generates a networkChangeEvents xml file
# Inputs - flood_network outputs


import pandas as pd
from datetime import datetime, timedelta


input_dir = "test/flood_network_outputs/"
output_xml = "test/generate_changeEvents_outputs/networkChangeEvents_test2.xml"
start_time = "12:00:00"
time_interval = "00:10:00"
time_format = "%H:%M:%S"
id_col = "ID"
velocity_col = "velocity"


def write_headers(file):
    file.write(f'<?xml version="1.0" encoding="UTF-8"?>\n')
    file.write(
        f'<networkChangeEvents xmlns="http://www.matsim.org/files/dtd" '
        f'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" '
        f'xsi:schemaLocation="http://www.matsim.org/files/dtd '
        f'http://www.matsim.org/files/dtd/networkChangeEvents.xsd">\n\n'
    )


def load_df(filepath):
    df = pd.read_csv(filepath)
    df = df[[id_col, velocity_col]]
    df = df.drop_duplicates(id_col)
    df = df[df[id_col].notna()]
    df = df[df[velocity_col].notna()] # TODO: Make sure there are no nan values coming from flooded_network
    df.sort_values(by=velocity_col, inplace=True, ascending=True)
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


def main():
    with open(output_xml, "w") as writefile:
        write_headers(writefile)
        current_time = start_time

        for i in range(1, 13):
            filename = f"NewcastleBaseline50mm_T{i}_{i}0min_flooded_network.csv"
            print(filename)
            filepath = input_dir + filename
            df = load_df(filepath)
            grouped = df.groupby(velocity_col)
            dfs = {value: df for value, df in grouped}


            for value, df in dfs.items():
                writefile.write(f'<networkChangeEvent startTime="{current_time}">\n')
                links = df["ID"].to_list()
                for link in links:
                    writefile.write(f'<link refId="{link}"/>\n')
                writefile.write(f'<freespeed type="absolute" value="{value}"/>\n')
                writefile.write("</networkChangeEvent>\n")

            current_time = calculate_time(current_time, time_interval, time_format)

        writefile.write(f'</networkChangeEvents>\n')

    print('Done')


if __name__ == "__main__":
    main()