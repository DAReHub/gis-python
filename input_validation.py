import re
import os


def network(filepath):
    print("checking for:", filepath)
    if not os.path.isfile(filepath):
        raise Exception("No network found - check your input path")


def floodRasters(filepath):
    """
    Validates a list of filenames based on the conditions:
    1. Filenames must follow the pattern '<prefix>_T<timestep>_<time>min.<valid_extension>'.
    2. Timesteps (T<number>) must be consecutive.

    Parameters:
    filenames (list): List of filenames to validate.

    Returns:
    bool: True if all files are valid, False otherwise.
    """

    if not os.listdir(filepath):
        raise Exception("No flood rasters found - check your input paths")

    # Regular expression pattern to match filenames like: "NewcastleBaseline50mm_T0_0min.tif"
    FILENAME_PATTERN = re.compile(
        r"(?P<prefix>.+)_T(?P<timestep>\d+)_(?P<time>\d+)min\.(?P<extension>tif|tfw|tif\.aux\.xml)"
    )

    # Parse filenames
    parsed_files = []

    for filename in os.listdir(filepath):
        match = FILENAME_PATTERN.match(filename)
        if not match:
            print(f"Invalid filename format: {filename}")
            raise Exception("Filename validation failed.")
        # Extract the parsed parts
        prefix = match.group("prefix")
        timestep = int(match.group("timestep"))
        time = int(match.group("time"))
        extension = match.group("extension")
        parsed_files.append((filename, prefix, timestep, time, extension))

        # Sort by timestep to check sequential order
        parsed_files.sort(key=lambda x: x[2])  # Sort by timestep

        # Check for sequential timesteps and validate filenames
        for i in range(1, len(parsed_files)):
            prev_file = parsed_files[i - 1]
            curr_file = parsed_files[i]

            # Check if the prefix is the same
            if prev_file[1] != curr_file[1]:
                print(
                    f"Prefix mismatch between files: {prev_file[0]} and {curr_file[0]}")
                raise Exception("Filename validation failed.")

            # Check if timesteps are consecutive
            if curr_file[2] != prev_file[2] + 1:
                print(
                    f"Non-consecutive timestep between files: {prev_file[0]} and {curr_file[0]}")
                raise Exception("Filename validation failed.")

        print("All files are valid.")
        return True


def main(filepath):
    floodRasters(filepath + "/flood_rasters/")
    network(filepath + '/network.gpkg')


if __name__ == "__main__":
    main("")
