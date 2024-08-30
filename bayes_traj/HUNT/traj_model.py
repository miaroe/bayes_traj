import pickle
import matplotlib.pyplot as plt
import pandas as pd

from bayes_traj.pyro_helper import *
from bayes_traj.generate_prior import run_generate_prior_with_args
from bayes_traj.viz_data_prior_draws import run_plot_from_args
from bayes_traj.bayes_traj_main import run_bayes_traj_with_args
from bayes_traj.viz_model_trajs import run_visualization_with_args

torch.set_default_dtype(torch.double)

data_path = '/Users/miarodde/Documents/Phd/Bayesian/Code/bayes_traj/bayes_traj/resources/data/HUNT/trajectory_data.csv'
preds = ['Intercept', 'Sex', 'PartAg']  # 'SmoPackYrs'
targets = ['FEV1ZSGLI']
num_trajs = '5-7'
group_by = 'PID_109925'
prior_file = 'prior_file.p'
tar_resid = 'FEV1ZSGLI,4,0.01'
out_model = 'model_file.p'
iters = '150'
num_draws = '10'
x_axis = 'PartAg'
y_axis = 'FEV1ZSGLI'


# ----------------- UTILITIES ----------------- #
def visualize_data(df):
    plt.scatter(df.PartAg.values, df.FEV1ZSGLI.values, facecolor='none', edgecolor='k', alpha=0.2)
    plt.xlabel('age', fontsize=16)
    plt.ylabel('fev1', fontsize=16)
    plt.show()


def plot_priors(data_file, prior_file, num_draws, y_axis, x_axis):
    '''
    # Ensure prior file is loaded correctly
    with open(prior_file, 'rb') as f:
        prior_file = pickle.load(f)
        print("Prior Info Loaded:")
        print(prior_file)
    '''

    args = [
        f'--data_file={data_file}',
        f'--prior={prior_file}',
        f'--num_draws={num_draws}',
        f'--y_axis={y_axis}',
        f'--x_axis={x_axis}',
    ]

    run_plot_from_args(args)


def plot_trajs(model_file, x_axis, y_axis):
    args = [
        f'--model={model_file}',
        f'--x_axis={x_axis}',
        f'--y_axis={y_axis}'
    ]

    run_visualization_with_args(args)


# ----------------- MAIN ----------------- #


def create_priors(data_path, preds, targets, num_trajs, prior_file, group_by, tar_resid, num_draws, y_axis, x_axis):
    df = pd.read_csv(data_path)
    print(df.head())

    # visualize_data(df)

    # Construct the arguments as a list of strings
    args = [
        f'--num_trajs={num_trajs}',
        f'--preds={",".join(preds)}',
        f'--targets={",".join(targets)}',
        f'--in_data={data_path}',
        f'--out_file={prior_file}',
        f'--groupby={group_by}',
        f'--tar_resid={tar_resid}',
    ]

    try:
        run_generate_prior_with_args(args)
    except RuntimeError as e:
        if 'Repository not up-to-date' in str(e):
            print("Warning: Repository not up-to-date. Skipping provenance tracking.")
        else:
            raise  # Re-raise the exception

    plot_priors(data_path, prior_file, num_draws, y_axis, x_axis)


create_priors(data_path, preds, targets, num_trajs, prior_file, group_by, tar_resid, num_draws, y_axis, x_axis)

def create_model(data_path, prior_file, targets, group_by, iters, model_file, x_axis, y_axis):
    args = [
        f'--in_csv={data_path}',
        f'--prior={prior_file}',
        f'--targets={",".join(targets)}',
        f'--groupby={group_by}',
        f'--iters={iters}',
        f'--verbose',
        f'--out_model={model_file}',
        f'--probs_weight=1',
    ]

    try:
        run_bayes_traj_with_args(args)
    except RuntimeError as e:
        if 'Repository not up-to-date' in str(e):
            print("Warning: Repository not up-to-date. Skipping provenance tracking.")
        else:
            raise  # Re-raise the exception

    plot_trajs(model_file, x_axis, y_axis)


create_model(data_path, prior_file, targets, group_by, iters, out_model, x_axis, y_axis)
