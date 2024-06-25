import pickle
import numpy as np
from argparse import ArgumentParser
import torch
import pdb
import bayes_traj
import pandas as pd


def load_model(file_path):
    """
    Load a model from the given file path. Determines the file type by 
    inspecting the file header and loads using appropriate method.

    Parameters
    ----------
        file_path : str
            Path to the model file.

    Returns
    -------
        model : object
            Instance of MultDPRegression or MultPyro
        
    """    
    # Try to load with pickle first
    try:
        with open(file_path, 'rb') as f:
            model = pickle.load(f)['MultDPRegression']
        print("Model loaded with pickle")
        
        return model
    except (pickle.UnpicklingError, AttributeError, EOFError, ImportError,
            IndexError):
        print("Pickle load failed. Trying torch...")

    # If pickle fails, try torch
    try:
        model = torch.load(file_path)
        print("Model loaded with torch")
        
        return model
    except Exception as e:
        print(f"Torch load failed: {e}")

    raise ValueError("Failed to load the model with both pickle and torch")
    

def augment_df_with_traj_info(df, model, traj_map=None):
    """Takes a pandas data frame as input and assigns each individual to their 
    most probable trajectory using the specified model.

    Parameters
    ----------
    df : pandas dataframe
        Dataframe contains the predictors and target variables that will be used
        to assign each individual to their most probable trajectory

    model : object
        MultDPRegression or MultPyro object that will be used to assign 
        trajectories

    traj_map : dict
        An integer-to-integer mapping from current trajectory numbers to 
        desired trajectory numbers
 
    Returns
    -------
    df_aug : pandas dataframe
        Corresponds to the input dataframe, but augmented with the columns:
        'traj' and 'traj_*'. 'traj' contains the most probable trajectory
         assignment; 'traj_*' columns record the probability of each of the
        trajectories.
    """
    if isinstance(model, bayes_traj.mult_dp_regression.MultDPRegression):
        if traj_map is None:
            traj_map = {}
            for ii in np.where(model.sig_trajs_)[0]:
                traj_map[ii] = ii
        
        R = model.get_R_matrix(df, model.gb_.grouper.names[0]).numpy()
        N = df.shape[0]
        # Now augment the dataframe with trajectory info
        traj = []
        for i in range(N):
            traj.append(traj_map[np.where(np.max(R[i, :]) == R[i, :])[0][0]])
        df['traj'] = traj

        for ss in np.where(model.sig_trajs_)[0]:
            df[f'traj_{traj_map[ss]}'] = R[:, ss]

        return df

    if isinstance(model, bayes_traj.mult_pyro.MultPyro):
        if traj_map is None:
            traj_map = {}
            for ii in np.range(model.K):
                traj_map[ii] = ii
                
        probs = model.classify(df)
        pdb.set_trace()
    

def get_pred_names_from_prior_info(prior_info):
    """Gets the list of predictor names used to construct a prior info 
    dictionary.

    Parameters
    ----------
    prior_info : dict
        Dictionary containing prior information. The dictionary structure is 
        equivalent to that produced by the generate_prior.py utility.

    Returns
    -------
    preds : list of strings
        List of predictor names
    
    """
    return list(list(prior_info['w_mu0'].values())[0].keys())


def get_target_names_from_prior_info(prior_info):
    """Gets the list of target names used to construct a prior info dictionary.

    Parameters
    ----------
    prior_info : dict
        Dictionary containing prior information. The dictionary structure is 
        equivalent to that produced by the generate_prior.py utility.

    Returns
    -------
    target : list of strings
        List of target names
    
    """
    return list(prior_info['w_mu0'].keys())


def sample_precs(lambda_a0, lambda_b0, num_samples):
    """Samples trajectory precision values given parameters describing the 
    distribution over precisions.

    Parameters
    ----------
    lambda_a0 : array, shape ( D )
        The first parameter of the gamma distribution over trajectory 
        precisions for each of the D target dimensions.

    lambda_b0 : array, shape ( D )
        The second parameter of the gamma distribution over trajectory 
        precisions for each of the D target dimensions.

    num_samples : int
        Number of samples to draw

    Returns
    -------
    prec : array, shape ( D, num_samples )
        The randomly generated trajectory precisions
    """
    assert lambda_a0.ndim == lambda_b0.ndim == 1,  \
        "Unexpected number of dimensions"
    
    D = lambda_a0.shape[0]

    prec = np.zeros([D, num_samples])
    for dd in range(D):
        scale_tmp = 1./lambda_b0[dd]
        shape_tmp = lambda_a0[dd]
        prec[dd, :] = np.random.gamma(shape_tmp, scale_tmp, num_samples)

    return prec


def sample_cos(w_mu0, w_var0, num_samples=1):
    """Samples trajectory coefficients given parameters describing the 
    distribution over coefficients

    Parameters
    ----------
    w_mu0 : array, shape ( M, D )
        The mean of the multivariate normal distribution over trajectoreis. M
        is the number of predictors, and D is the number of dimensions.

    w_var0 : array, shape ( M, D )
        The variances of the Normal distributions over the trajectory 
        coefficients.

    num_samples : int , optional
        Number of samples to draw

    Returns
    -------
    w : array, shape ( M, D, num_samples )
        The randomly generated trajectory coefficients    
    """
    assert w_mu0.ndim == w_var0.ndim == 2, \
        "Unexpected number of dimensions"
    
    M = w_mu0.shape[0]
    D = w_mu0.shape[1]

    assert w_var0.shape[0] == M and w_var0.shape[1] == D, \
        "Unexpected shape"

    w = np.zeros([M, D, num_samples])
    for mm in range(M):
        for dd in range(D):
            w[mm, dd, :] = w_mu0[mm, dd] + \
                np.sqrt(w_var0[mm, dd])*np.random.randn(num_samples)

    return w


def sample_traj(w_mu0, var_covar0, lambda_a0, lambda_b0, num_samples):
    """Samples a trajectory given an input description of the distribution over
    trajectories. A sampled trajectory is represented in terms of predictor
    coefficients (w_mu) and precision values for each dimension.

    Parameters
    ----------
    w_mu0 : array, shape ( M, D )
        The mean of the multivariate normal distribution over trajectoreis. M
        is the number of predictors, and D is the number of dimensions.

    var_covar : array, shape ( M, D ) or ( MxD, MxD )
        The variance (covariance) of the multivariate normal distribution over
        trajectories. If the shape is equivalent to that of w_mu0, the elements
        will be taken as diagonal elements of the multivariate's covariance
        matrix. Otherwise, the matrix is expected to be a full MxD by MxD 
        covariance matrix.

    lambda_a0 : array, shape ( D )
        The first parameter of the gamma distribution over trajectory 
        precisions for each of the D target dimensions.

    lambda_b0 : array, shape ( D )
        The second parameter of the gamma distribution over trajectory 
        precisions for each of the D target dimensions.

    num_samples : int
        Number of samples to draw

    Returns
    -------
    w : array, shape ( M, D, num_samples )
        The randomly generated trajectory coefficients    

    precs : array, shape ( D, num_samples )
        The randomly generated trajectory precisions
    """

    w = sample_cos(w_mu0, var_covar0, num_samples)
    precs = sample_precs(lambda_a0, lambda_b0, num_samples)

    return w, precs
