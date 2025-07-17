"Takes UKCP NETCDF file and converts to Rainfall_Data suitable for CityCAT"

import numpy as np
from netCDF4 import Dataset
import matplotlib as mplt
import cartopy.crs as ccrs
import cartopy.feature as cfea
import matplotlib.pyplot as plt
from pathlib import Path
import argparse

def write_headers(filepath, tttn, iii, caseid):
    with open(filepath, 'w') as fcat:
        fcat.write('* * *\n')
        fcat.write('* * * rainfall * * *\n')
        fcat.write('* * * case id: ' + caseid + '\n')
        fcat.write(str(tttn) + '\n')
        fcat.write('* * * ' + iii + '\n')


def write_data(output_filepath, prec, seconds):
    prec *= 2.7777777777778E-7  # convert to m/s
    format2prec = ' '.join(' '.join('%0.12f' % x for x in y) for y in prec)
    reshape = np.ravel(str(format2prec))
    reshape = ' '.join(map(str, reshape))
    with open(output_filepath, 'a') as fcat:
        fcat.write(f"{seconds} {reshape}\n")


def write_figure(
    output_dir, region, lat, lon, prec, ttt, pole_longitude, pole_latitude
):

    output = output_dir / str(ttt)
    print('Plotting:', output)

    domains = {
        "Newcastle": [-0.10, 1.00, 2.00, 2.90],
        "Manchester": [-0.60, 0.60, 0.5, 1.5],
        "UK": [-6.93, 5.17, -5.5467, 8.9268],
        "EU": [-18.8, 11.9, -14.8, 15.9],
    }

    mplt.rc('xtick', labelsize=9)
    mplt.rc('ytick', labelsize=9)

    projection = ccrs.RotatedPole(pole_longitude, pole_latitude)

    fig = plt.figure(figsize=(5, 6))
    ax = fig.add_subplot(1, 1, 1, projection=projection)
    ax.set_extent(domains[region], projection)
    ax.add_feature(cfea.COASTLINE.with_scale('10m'), lw=.5)
    ax.add_feature(cfea.BORDERS.with_scale('10m'), linewidth=0.5, edgecolor='dimgray')
    ax.add_feature(cfea.STATES.with_scale('10m'), linewidth=0.5, edgecolor='dimgray')
    ax.patch.set_facecolor('.9')
    ax.add_feature(cfea.LAND)

    # levels=[0,4,8,12,16,20,24,28,32,36,40] #,22,24,26,28,30]
    levels = [0, 2, 4, 8, 16, 32, 64, 128]
    cmap = plt.cm.viridis_r
    norm = mplt.colors.BoundaryNorm(levels, cmap.N)
    # norm=mplt.colors.Normalize(vmin=None,vmax=None, clip=False)
    # norm = mplt.colors.Normalize(vmin=0, vmax=1)
    pc = ax.contourf(
        lon, lat, prec[:, :], levels=levels, transform=projection,
        cmap=cmap, norm=norm, extend='max'
    )
    # pc=ax.contourf(lon,lat,prec,levels=levels,transform=projection,cmap=cmap,norm=norm,extend='max')
    # fig.colorbar(pc,extend='max', cax=ax_cb)
    # fig.add_axes(ax_cb)

    ax.gridlines(draw_labels=True, dms=True, x_inline=False, y_inline=False,
                 color='black', linestyle='--')

    ttitle = 'Precipitation'
    ax.set_title(ttitle, loc='left', fontsize=12)

    fig.subplots_adjust(bottom=0.10)
    ax_cb1 = fig.add_axes([0.20, 0.08, 0.60, 0.011])
    fig.colorbar(pc, cax=ax_cb1, orientation='horizontal')
    ax_cb1.tick_params(labelsize=12)
    ax_cb1.set_xlabel('Precipitation [$mm h^{-1}$]')

    # ax_cb1d = fig.add_axes([0.439, 0.08, 0.15, 0.011])
    # fig.colorbar(pc1d, cax=ax_cb1d, orientation='horizontal')
    # ax_cb1d.tick_params(labelsize=12)
    # ax_cb1d.set_xlabel('Change in lightning flashes [$km^{-2}$]')

    # plt.tight_layout()
    plt.subplots_adjust(wspace=0.04, hspace=0.08)

    plt.savefig(output.with_suffix('.png'))

    formatprec = '\n'.join('\t'.join('%0.12f' % x for x in y) for y in prec)
    with open(output.with_suffix('.txt'), 'w') as f:
        f.write(str(formatprec))

    # code piece below writes lats and lons for each file
    #
    # strlat=str(lat)
    # strlon=str(lon)
    # with open('mantest/'+caseid+strttt+'lat.txt', 'w') as f:
    #    f.write(strlat)
    # with open('mantest/'+caseid+strttt+'lon.txt', 'w') as f:
    #    f.write(strlon)

    # precase(tttnum)=prec


def main(
        input_filepath: str,
        output_dir: str,
        start_val: int,
        end_val: int,
        ngrid: int,
        caseid: str,
        pole_longitude: float = None,
        pole_latitude: float = None,
        region: str = None,
        plot: bool = False,
):

    input_filepath = Path(input_filepath)
    output_dir = Path(output_dir)
    output_dir = output_dir / caseid
    output_dir.mkdir(parents=True, exist_ok=True)
    output = (output_dir / "Spatial_Rainfall_Data").with_suffix(".txt")

    dosya = Dataset(input_filepath, 'r')

    ttt = start_val
    tttend = end_val
    tttilk = ttt
    tttn = tttend - ttt

    iii = list(range(1, ngrid**2 + 1))
    iii = ' '.join(map(str, iii))
    write_headers(output, tttn, iii, caseid)

    while ttt < tttend:
        tttnum = ttt - tttilk
        seconds = 1800 * tttnum
        lat = dosya.variables['grid_latitude'][:]
        lon = dosya.variables['grid_longitude'][:]
        prec = (dosya.variables['precipitation_flux'][ttt, :, :])

        write_data(output, prec, seconds)

        if plot:
            write_figure(
                output_dir, region, lat, lon, prec, ttt, pole_longitude,
                pole_latitude
            )

        ttt += 1

    print("Done")


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument(
        '--netcdf_filepath',
        required=True,
        type=str
    )
    p.add_argument(
        '--output_dir',
        required=False,
        default=".",
        type=str
    )
    p.add_argument(
        '--caseid',
        required=True,
        type=str,
        help="(required) Give your case an ID"
    )
    p.add_argument(
        '--start_val',
        required=True,
        type=int,
    )
    p.add_argument(
        '--end_val',
        required=True,
        type=int,
    )
    p.add_argument(
        '--ngrid',
        required=True,
        type=int,
        help="provided value is squared to form a grid"
    )
    p.add_argument(
        '--pole_longitude',
        required=False,
        type=float,
        default=177.5,
        help="Only required if plotting. Defaults to 177.5"
    )
    p.add_argument(
        '--pole_latitude',
        required=False,
        type=float,
        default=37.5,
        help="Only required if plotting. Defaults to 37.5"
    )
    p.add_argument(
        '--plot',
        required=False,
        action='store_true',
        help="Include to plot results"
    )
    p.add_argument(
        '--region',
        required=False,
        choices=['Newcastle', 'Manchester', 'UK', 'EU'],
        type=str,
        help="Only required if plotting",
        default=None
    )
    args = p.parse_args()

    main(
        input_filepath=args.netcdf_filepath,
        output_dir=args.output_dir,
        region=args.region,
        plot=args.plot,
        caseid=args.caseid,
        start_val=args.start_val,
        end_val=args.end_val,
        ngrid=args.ngrid,
        pole_longitude=args.pole_longitude,
        pole_latitude=args.pole_latitude
    )
