import os, sys
import numpy as np
import scipy.constants as sc
from scipy.special import ellipk, ellipe
from scipy import integrate
from scipy.interpolate import interp1d


### MODEL
# Keplerian + self-gravity model (Veronesi et al.)
# r is in AU
# pars = [Mstar, Mdisk, log(f)]
def model_vphi(r, pars):

    # definitions (i.e., fixed parameters)
    dpc = 150.
    ps = np.array([0.29723454, 1.28063122, 2.17227701, 5.60994904])
    r0, rd, pp, gam = 10., 160., 1.0, 2.0
    #Tmid0, Tatm0, qq, a_z, w_z = 40., 160., 0.5, 0.20, 0.05
    Tmid0, Tatm0, qq, a_z, w_z = 50., 170., 0.5, 0.25, 0.05
    mu, mH = 2.37, (sc.m_e + sc.m_p)

    # rprime, zprime grids
    r_, z_ = np.linspace(0.5, 300.5, 301), np.logspace(-1.5, 2, 201)
    rr, zz = np.meshgrid(r_ * sc.au, z_ * sc.au)

    ### compute the Keplerian angular velocity
    #om_kep2 = sc.G * pars[0] * 1.9891e30 / np.hypot(rr, zz)**3
    zCO = dpc * ps[0] * (r/dpc)**ps[1] * np.exp(-(r/(dpc * ps[2]))**ps[3])
    om_kep2 = sc.G * pars[0] * 1.9891e30 / np.hypot(r * sc.au, zCO * sc.au)**3

    ### compute an approximation for the pressure support term
    # 2-d temperature structure
    Tmid = Tmid0 * (rr / (r0 * sc.au))**-qq
    Tatm = Tatm0 * (rr / (r0 * sc.au))**-qq
    fz = 0.5 * np.tanh(((zz / rr) - a_z) / w_z) + 0.5
    Tgas = Tmid + fz * (Tatm - Tmid)
    Tgas = np.clip(Tgas, a_min=0., a_max=1000)
    cs = np.sqrt(sc.k * Tgas / (mu * mH))

    # vertical log(sound speed) gradient
    dlnc, dz = np.diff(np.log(cs), axis=0), np.diff(zz, axis=0)
    dlncdz = np.row_stack((dlnc, dlnc[-1,:])) / np.row_stack((dz, dz[-1,:]))

    # vertical gravity from star
    gz_star = zz * sc.G * pars[0] * 1.9891e30 / np.hypot(rr, zz)**3

    # gas surface density
    sigma_ = (r_ / r0)**-pp * np.exp(-(r_ / rd)**gam)
    snorm_ = pars[1] * 1.9891e30 / \
             np.trapz(2 * np.pi * sigma_ * r_ * sc.au, r_ * sc.au)
    sigma = snorm_ * sigma_

    # vertical gravity from disk
    gz_disk = 2 * np.pi * sc.G * sigma

    # total vertical gravity
    gz = gz_star + gz_disk
   
    # vertical log(density) gradient
    dlnpdz = -gz / cs**2 - 2 * dlncdz

    # numerical integration to log(density) [un-normalized]
    lnp = integrate.cumtrapz(dlnpdz, zz, initial=0, axis=0)
    rho0 = np.exp(lnp)

    # normalize
    rho = 0.5 * rho0 * sigma
    rho /= integrate.trapz(rho0, zz, axis=0)
    rho = np.clip(rho, a_min=100 * mu * mH * 1e6, a_max=1e50)

    # log(density) radial gradient
    dlnrhodr = np.gradient(np.log(rho), rr[0,:], axis=1)

    # sound speed radial gradient
    dcdr = np.gradient(cs, rr[0,:], axis=1)

    # pressure support term (full 2-d grid)
    epsP_grid = cs**2 * dlnrhodr / rr + 2 * cs * dcdr / rr


    ### compute the non-Keplerian contribution from self-gravity
    # rprime grid
    rp = np.logspace(0, 3, 512)

    # k coordinate
#    kk = np.sqrt(4 * rp[None, :] * rr[:, :, None] / \
#                 ((rr[:,:,None] + rp[None,:])**2 + zz[:,:,None]**2))

    # g(k)
#    gk = ellipk(kk) - 0.25 * (kk**2 / (1. - kk**2)) * \
#         ((rp[None, :] / rr[:, :, None]) - (rr[:, :, None] / rp[None, :]) + \
#          (zz[:,:,None]**2 / (rr[:,:,None] * rp[None,:]))) * ellipe(kk)

    # field integrand
#    sigma_ = (rp / (r0 * sc.au))**-pp * np.exp(-(rp / (rd * sc.au))**gam)
#    snorm_ = pars[1] * 1.9891e30 / np.trapz(2 * np.pi * sigma_ * rp, rp)
#    sigma = snorm_ * sigma_
#    finteg = gk * np.sqrt(rp[None,:] / rr[:,:,None]) * kk * sigma[None,:]

    # field
#    dPhidr = sc.G * np.trapz(finteg, rp, axis=-1) / rr

    # self-gravity contribution
#    epsg_grid = dPhidr / rr

    # k coordinate
    kk = np.sqrt(4 * rp * r[:, None] / \
                 ((r[:,None] + rp)**2 + zCO[:,None]**2))

    # xi(k)
    xik = ellipk(kk) - 0.25 * (kk**2 / (1. - kk**2)) * \
          ((rp / r[:, None]) - (r[:, None] / rp) + \
           (zCO[:,None]**2 / (r[:,None] * rp))) * ellipe(kk)

    # gas surface density on rprime grid
    sigma_ = (rp / r0)**-pp * np.exp(-(rp / rd)**gam)
    snorm_ = pars[1] * 1.9891e30 / \
             np.trapz(2 * np.pi * sigma_ * rp * sc.au, rp * sc.au)
    sigma = snorm_ * sigma_

    # field integrand
    finteg = xik * np.sqrt(rp / r[:,None]) * kk * sigma

    # field
    dPhidr = sc.G * np.trapz(finteg, rp * sc.au, axis=-1) / (r * sc.au)

    # self-gravity contribution
    eps_g = dPhidr / (r * sc.au)



    ### interpolate epsilon_P onto the emission surface
    # assign the CO emission surface 
    zCO = dpc * ps[0] * (r_/dpc)**ps[1] * np.exp(-(r_/(dpc * ps[2]))**ps[3])

    # interpolate vertically onto that surface
    #omtot_grid = np.sqrt(om_kep2 + epsP_grid + epsg_grid)
    epsilon_P = np.empty_like(zCO)
    for ir in range(len(zCO)):
        vzint = interp1d(z_, epsP_grid[:,ir], fill_value='extrapolate')
        epsilon_P[ir] = vzint(zCO[ir])

    # interpolate radially onto specified points
    vrint = interp1d(r_, epsilon_P, fill_value='extrapolate')
    eps_p = vrint(r)

    # calculate full-res radial velocity profile
    omtot2 = om_kep2 + eps_p + eps_g
    omtot2[omtot2 < 0] = 0
    vel_r = r * sc.au * np.sqrt(omtot2)

    return vel_r
