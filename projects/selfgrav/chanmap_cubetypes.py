import os, sys, importlib
sys.path.append('../../')
sys.path.append('../../configs/')
import numpy as np
import scipy.constants as sc
from astropy.io import fits
import matplotlib.pyplot as plt
from matplotlib.colorbar import Colorbar
from matplotlib import mlab, cm
from matplotlib.patches import Ellipse
from astropy.visualization import (AsinhStretch, LogStretch, ImageNormalize)
import cmasher as cmr

# style setups
from matplotlib.colorbar import Colorbar
from mpl_toolkits.axes_grid1 import make_axes_locatable
import cmasher as cmr
from matplotlib import cm, font_manager
plt.style.use(['default', '/home/sandrews/mpl_styles/nice_line.mplstyle'])
font_dirs = ['/home/sandrews/extra_fonts/']
font_files = font_manager.findSystemFonts(fontpaths=font_dirs)
for font_file in font_files:
    font_manager.fontManager.addfont(font_file)
plt.rcParams['font.family'] = 'Helvetica'


# model to plot
mdl = 'taper2hi'


# load input parameter dictionary
inp = importlib.import_module('gen_sg_'+mdl)


# cube files
cdir = inp.reduced_dir+inp.basename+'/images/'
cfiles = [inp.radmcname+'/raw_cube.fits',
          cdir+inp.basename+'_pure.DATA.image.fits',
          cdir+inp.basename+'_noisy.DATA.image.fits']
clbls = ['raw', 'sampled', 'noisy']

left, right, bottom, top, hsp, wsp = 0.055, 0.92, 0.155, 0.99, 0.05, 0.05


# display properties
vmin, vmax = 0, 60
nchans, ch0, dch = 9, 74, 1
xlims = np.array([2.1, -2.1])
cm = 'cmr.eclipse'
norm = ImageNormalize(vmin=vmin, vmax=vmax, stretch=AsinhStretch())

fig, axs = plt.subplots(nrows=3, ncols=nchans, figsize=(7.5, 2.60))

for ic in range(len(cfiles)):

    # load the cube and header
    hdu = fits.open(cfiles[ic])
    Ico, hd = np.squeeze(hdu[0].data), hdu[0].header
    hdu.close()

    # define coordinate grids
    dx = 3600 * hd['CDELT1'] * (np.arange(hd['NAXIS1']) - (hd['CRPIX1'] - 1))
    dy = 3600 * hd['CDELT2'] * (np.arange(hd['NAXIS2']) - (hd['CRPIX1'] - 1))
    ext = (np.max(dx), np.min(dx), np.min(dy), np.max(dy))

    # define beam areas (and dimensions for imaged cases)
    if ic == 0:
        bm = np.abs(np.diff(dx)[0]*np.diff(dy)[0])*(np.pi/180)**2 / 3600**2
    else:
        bmaj, bmin, bpa = 3600 * hd['BMAJ'], 3600 * hd['BMIN'], hd['BPA']
        print(bmaj, bmin, bpa)
        bm = (np.pi * bmaj * bmin / (4 * np.log(2))) * (np.pi/180)**2 / 3600**2

    # set up a row of channel maps
    for iv in range(nchans):

        # convert this channel map into brightness temperature
        nu = hd['CRVAL3'] + (dch*iv + ch0) * hd['CDELT3']
        v = sc.c * (1 - nu / 230.538e9)
        Tb = (1e-26*Ico[(dch*iv + ch0),:,:] / bm) * sc.c**2 / (2 * sc.k * nu**2)

        # plot the channel map
        ax = axs[ic, iv]
        im = ax.imshow(Tb, origin='lower', cmap=cm, extent=ext, aspect='equal',
                       norm=norm)

        # labels
        if iv == 0:
            ax.text(0.02, 0.90, clbls[ic], transform=ax.transAxes, ha='left',
                    va='center', style='italic', fontsize=7, color='w')
        if ic == 0:
            if np.abs(v) < 0.001: v = 0.0
            if np.logical_or(np.sign(v) == 1, np.sign(v) == 0):
                pref = '+'
            else: 
                pref = ''
            vstr = pref+'%.2f' % (1e-3 * v)
            ax.text(0.97, 0.92, vstr, transform=ax.transAxes, ha='right',
                    va='center', fontsize=6, color='w')

        # beam dimensions
        if ic > 0:
            beam = Ellipse((xlims[0] + 0.1*np.diff(xlims),
                            -xlims[0] - 0.1*np.diff(xlims)), bmaj, bmin, 90-bpa)
            beam.set_facecolor('w')
            ax.add_artist(beam)

        # modify the styling
        ax.set_xlim(xlims)
        ax.set_ylim(-xlims)
        if np.logical_and(ic == 2, iv == 0):
            ax.set_yticks([-2, 0, 2])
            ax.set_xlabel('$\Delta \\alpha$  ($^{\prime\prime}$)')
            ax.set_ylabel('$\Delta \\delta$  ($^{\prime\prime}$)', labelpad=2)
        else:
            ax.tick_params(axis='both', which='both', length=0)
            ax.set_xticklabels([])
            ax.set_yticklabels([])

# colorbar
cbax = fig.add_axes([right+0.01, bottom+0.01, 0.01, top-bottom-0.02])
cb = Colorbar(ax=cbax, mappable=im, orientation='vertical',
              ticklocation='right')
cb.set_label('$T_{\\rm b}$  (K)', rotation=270, labelpad=13)


fig.subplots_adjust(left=left, right=right, bottom=bottom, top=top,
                    hspace=hsp, wspace=hsp)
fig.savefig('figs/chanmap_cubetypes.pdf')
fig.clf()
