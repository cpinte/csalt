# Import libraries
import os, sys
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from csalt.model import *
from csalt.helpers import *
import multiprocessing
from functools import partial

# Class definition
class setup_fit():

    def __init__(self,
                 msfile=None,
                 append: bool = False,
                 mpi: bool = False,
                 param=None,
                 vra_fit=[4.06e3, 8.06e3],
                 vsyst=None,
                 vcensor=None,
                 nwalk=128,
                 ninits=300,
                 nsteps=5000,
                 nthreads=32,
                 nu_rest=345.796e9,
                 FOV=6.375,
                 Npix=256,
                 dist=144.5,
                 cfg_dict={}):
        
        if msfile is None:
            print('Need to give an ms file as input!')
            return
        
        # code is mcfost
        self.mtype = 'MCFOST'
        
        self.vra_fit = vra_fit
        self.vcensor = vcensor
        # I/O
        self.datafile = msfile
        # Inference Setups
        self.nwalk = nwalk
        self.ninits = ninits
        self.nsteps = nsteps
        self.nthreads = nthreads
        self.append = append
        # Fixed Parameters
        self.nu_rest = nu_rest
        self.FOV = FOV
        self.Npix = Npix
        self.dist = dist
        self.cfg_dict = cfg_dict
        self.mpi = mpi
        self.param = None
        self.vsyst = vsyst

        if param is not None:
            print('Using param!')
            self.param = param
            self.priors_prescription = self.mtype
            for parameter in self.param:
                self.priors_prescription += '_'+parameter
        else:
            self.priors_prescription = self.mtype

        # Instantiate a csalt model
        print('Making model')
        self.cm = model(self.mtype)
        self.cm.param = self.param

        # Define some fixed attributes for the modeling
        self.fixed_kw = {'FOV': self.FOV, 'Npix': self.Npix, 'dist': self.dist, 'vsyst': self.vsyst} 

        # Import priors
        print('Initialising priors')
        self.priors = importlib.import_module('priors_'+self.priors_prescription)
        self.Ndim = len(self.priors.pri_pars)             


    def mcmc_fit(self):
        """
        Performs mcmc fit of data visibilities with models as specified in setup
        No extra parameters required
        """
        
        self.cm.sample_posteriors(self.msfile, kwargs=self.fixed_kw,
                         vra=self.vra_fit, restfreq=self.nu_rest, 
                         Nwalk=75, Nthreads=6, Ninits=10, Nsteps=50,
                         outpost='DMTau_EB3.DATA.h5', param=None)
        

    def initialise(self):
        """
        Initialises the mcmc such that you could pass in a theta array and obtain a
        single log likelihood value etc.
        """
        
        infdata = self.cm.fitdata(self.datafile, vra=self.vra_fit, restfreq=self.nu_rest)
        p0 = self.cm.mcfost_priors(self.priors, self.nwalk, self.Ndim)
        infdata = self.cm.cache(p0, infdata, self.nu_rest, self.fixed_kw)
        return infdata
    

    def get_probability(self, infdata, theta):
        """
        Returns the log probability of a specific theta array fitting the data
        Need to run initialise function first
        """

        global fdata
        global kw
        fdata = copy.deepcopy(infdata)
        kw = copy.deepcopy(self.fixed_kw)

                # Populate keywords from kwargs dictionary
        if 'restfreq' not in kw:
            kw['restfreq'] = self.nu_rest
        if 'FOV' not in kw:
            kw['FOV'] = 5.0
        if 'Npix' not in kw:
            kw['Npix'] = 256
        if 'dist' not in kw:
            kw['dist'] = 150.
        if 'chpad' not in kw:
            kw['chpad'] = 2
        if 'Nup' not in kw:
            kw['Nup'] = None
        if 'noise_inject' not in kw:
            kw['noise_inject'] = None
        if 'doppcorr' not in kw:
            kw['doppcorr'] = 'approx'
        if 'SRF' not in kw:
            kw['SRF'] = 'ALMA'


        loglikelihood = self.cm.log_likelihood(theta, fdata=fdata, kwargs=kw)

        priors = importlib.import_module('priors_'+self.priors_prescription)
        lnT = np.sum(priors.logprior(theta)) * fdata['Nobs']
        print('Priors', lnT)

        return loglikelihood+lnT
    

    def brute_force(self, data):

        """
        Needs to be called after initialise
        """

        global fdata
        global kw
        fdata = copy.deepcopy(data)
        kw = copy.deepcopy(self.fixed_kw)

        # Populate keywords from kwargs dictionary
        if 'restfreq' not in kw:
            kw['restfreq'] = self.nu_rest
        if 'FOV' not in kw:
            kw['FOV'] = 5.0
        if 'Npix' not in kw:
            kw['Npix'] = 256
        if 'dist' not in kw:
            kw['dist'] = 150.
        if 'chpad' not in kw:
            kw['chpad'] = 2
        if 'Nup' not in kw:
            kw['Nup'] = None
        if 'noise_inject' not in kw:
            kw['noise_inject'] = None
        if 'doppcorr' not in kw:
            kw['doppcorr'] = 'approx'
        if 'SRF' not in kw:
            kw['SRF'] = 'ALMA'

        self.values = []

        if self.param == 'PA':
            for i in range(360):
                self.values.append([i])
        elif self.param == 'stellar_mass':
            for i in range(100):
                self.values.append([0.2+i/250])
        elif self.param == 'vturb':
            for i in range(100):
                self.values.append([i/500])
        elif self.param == 'dust_param':
            for i in range(100):
                self.values.append([10**(i/50)])
        else:
            print("Caitlyn you haven't set that one up yet")
            return
        
        
        os.environ["OMP_NUM_THREADS"] = "1"
        with multiprocessing.Pool(processes=self.nthreads) as pool:
            ln_posteriors = pool.starmap(self.cm.log_likelihood, [(value, fdata, kw, None, self.param) for value in self.values])

        plt.figure()
        plt.plot(self.values, ln_posteriors)
        plt.title('Log posterior as a function of ' + self.param)
        plt.xlabel(self.param)
        plt.ylabel('Log posterior')
        plt.savefig(self.param+'lnposterior.pdf')


    

    # def plot_visibilities(self, data, theta, mcube=None):
    #     """
    #     Plots the difference between the model visibilities and data visibilities
    #     by EB for given polarisation and channel
    #     Need to run initialise function first
    #     """
    #     plot(data, self.fixed, self.mtype, theta, mcube)

    # def model_to_model(self, theta):
    #     """
    #     Runs a model to model fit so we can verify that the method is working
    #     """
    #     if self.mtype == 'MCFOST':
    #         from csalt.data_mcfost import fitdata
    #     data = fitdata(self.datafile, vra=self.vra_fit, nu_rest=self.nu_rest, chbin=3)
    #     p0 = [theta]
    #     data = build_cache(p0, data, self.fixed, code=self.mtype, mode=self.mode)

    #     model_vis = get_model_vis(theta, data, self.fixed, code_=self.mtype, mpi=self.mpi)

    #     run_emcee(self.datafile, self.fixed, code=self.mtype, vra=self.vra_fit,
    #               vcensor=self.vcensor, nwalk=self.nwalk, ninits=self.ninits,
    #               nsteps=self.nsteps, outfile=self.post_dir+self.postfile,
    #               mode=self.mode, nthreads=self.nthreads, append=self.append,
    #               mpi=self.mpi, model_vis=model_vis)
