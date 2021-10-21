import os
from typing import Optional, List
import click
import bn3d
from tqdm import tqdm
import numpy as np
import json
from .app import run_file
from .config import CODES, ERROR_MODELS, DECODERS, BN3D_DIR
from .slurm import (
    generate_sbatch, get_status, generate_sbatch_nist, count_input_runs,
    clear_out_folder, clear_sbatch_folder
)
from .noise import get_direction_from_bias_ratio


@click.group(invoke_without_command=True)
@click.version_option(version=bn3d.__version__, prog_name='bn3d')
@click.pass_context
def cli(ctx):
    """
    bn3d - biased noise in 3D simulations.

    See bn3d COMMAND --help for command-specific help.
    """
    if not ctx.invoked_subcommand:
        print(ctx.get_help())


@click.command()
@click.pass_context
@click.option('-f', '--file', 'file_')
@click.option('-t', '--trials', default=100, type=click.INT, show_default=True)
@click.option('-s', '--start', default=None, type=click.INT, show_default=True)
@click.option(
    '-o', '--output_dir', default=BN3D_DIR, type=click.STRING,
    show_default=True
)
@click.option(
    '-n', '--n_runs', default=None, type=click.INT, show_default=True
)
def run(
    ctx,
    file_: Optional[str],
    trials: int,
    start: Optional[int],
    n_runs: Optional[int],
    output_dir: Optional[str]
):
    """Run a single job or run many jobs from input file."""
    if file_ is not None:
        run_file(
            os.path.abspath(file_), trials,
            start=start, n_runs=n_runs, progress=tqdm,
            output_dir=output_dir
        )
    else:
        print(ctx.get_help())


@click.command()
@click.argument('model_type', required=False, type=click.Choice(
    ['codes', 'noise', 'decoders'],
    case_sensitive=False
))
def ls(model_type=None):
    """List available codes, noise models and decoders."""
    if model_type is None or model_type == 'codes':
        print('Codes:')
        print('\n'.join([
            '    ' + name for name in sorted(CODES.keys())
        ]))
    if model_type is None or model_type == 'noise':
        print('Error Models (Noise):')
        print('\n'.join([
            '    ' + name for name in sorted(ERROR_MODELS.keys())
        ]))
    if model_type is None or model_type == 'decoders':
        print('Decoders:')
        print('\n'.join([
            '    ' + name for name in sorted(DECODERS.keys())
        ]))


def read_bias_ratios(eta_string: str) -> list:
    """Read bias ratios from comma separated string."""
    bias_ratios = []
    for s in eta_string.split(','):
        s = s.strip()
        if s == 'inf':
            bias_ratios.append(np.inf)
        elif float(s) % 1 == 0:
            bias_ratios.append(int(s))
        else:
            bias_ratios.append(float(s))
    return bias_ratios


def read_range_input(specification: str) -> List[float]:
    """Read range input string and return list."""
    values: List[float] = []
    if ':' in specification:
        parts = specification.split(':')
        min_value = float(parts[0])
        max_value = float(parts[1])
        step = 0.005
        if len(parts) == 3:
            step = float(parts[2])
        values = np.arange(min_value, max_value + step, step).tolist()
    elif ',' in specification:
        values = [float(s) for s in specification.split(',')]
    else:
        values = [float(specification)]
    return values


@click.command()
@click.option(
    '-i', '--input_dir', required=True, type=str,
    help='Directory to save input .json files'
)
@click.option(
    '-l', '--lattice', required=True,
    type=click.Choice(['rotated', 'kitaev']),
    help='Lattice rotation'
)
@click.option(
    '-b', '--boundary', required=True,
    type=click.Choice(['toric', 'planar']),
    help='Boundary conditions'
)
@click.option(
    '-d', '--deformation', required=True,
    type=click.Choice(['none', 'xzzx', 'xy']),
    help='Deformation'
)
@click.option(
    '-r', '--ratio', default='equal', type=click.Choice(['equal', 'coprime']),
    show_default=True, help='Lattice aspect ratio spec'
)
@click.option(
    '--decoder', default='BeliefPropagationOSDDecoder',
    show_default=True,
    type=click.Choice(DECODERS.keys()),
    help='Decoder name'
)
@click.option(
    '-s', '--sizes', default='5,9,7,13', type=str,
    show_default=True,
    help='List of sizes'
)
@click.option(
    '--bias', default='Z', type=click.Choice(['X', 'Y', 'Z']),
    show_default=True,
    help='Pauli bias'
)
@click.option(
    '--eta', default='0.5,1,3,10,30,100,inf', type=str,
    show_default=True,
    help='Bias ratio'
)
@click.option(
    '--prob', default='0:0.6:0.005', type=str,
    show_default=True,
    help='min:max:step or single value or list of values'
)
def generate_input(
    input_dir, lattice, boundary, deformation, ratio, sizes, decoder, bias,
    eta, prob
):
    """Generate the json files of every experiment.

    \b
    Example:
    bn3d generate-input -i /path/to/inputdir \\
            -l rotated -b planar -d xzzx -r equal \\
            -s 2,4,6,8 --decoder BeliefPropagationOSDDecoder \\
            --bias Z --eta '10,100,1000,inf' \\
            --prob 0:0.5:0.005
    """

    if lattice == 'kitaev' and boundary == 'planar':
        raise NotImplementedError("Kitaev planar lattice not implemented")

    delta = 0.005
    probabilities = np.arange(0, 0.5+delta, delta).tolist()
    probabilities = read_range_input(prob)
    bias_ratios = read_bias_ratios(eta)
    for eta in bias_ratios:
        direction = get_direction_from_bias_ratio(bias, eta)
        for p in probabilities:
            label = "regular" if deformation == "none" else deformation
            label += f"-{lattice}"
            label += f"-{boundary}"
            if eta == np.inf:
                label += "-bias-inf"
            else:
                label += f"-bias-{eta:.2f}"
            label += f"-p-{p:.3f}"

            code_model = ''
            if lattice == 'rotated':
                code_model += 'Rotated'
            if boundary == 'toric':
                code_model += 'Toric'
            else:
                code_model += 'Planar'
            code_model += 'Code3D'

            L_list = [int(s) for s in sizes.split(',')]
            if ratio == 'coprime':
                code_parameters = [
                    {"L_x": L, "L_y": L + 1, "L_z": L}
                    for L in L_list
                ]
            else:
                code_parameters = [
                    {"L_x": L, "L_y": L, "L_z": L}
                    for L in L_list
                ]
            code_dict = {
                "model": code_model,
                "parameters": code_parameters
            }

            if deformation == "none":
                noise_model = "PauliErrorModel"
            elif deformation == "xzzx":
                noise_model = 'DeformedXZZXErrorModel'
            elif deformation == "xy":
                noise_model = 'DeformedXYErrorModel'

            noise_parameters = direction
            noise_dict = {
                "model": noise_model,
                "parameters": noise_parameters
            }

            if decoder == "BeliefPropagationOSDDecoder":
                decoder_model = "BeliefPropagationOSDDecoder"
                decoder_parameters = {'joschka': True,
                                      'max_bp_iter': 10}
            else:
                decoder_model = decoder
                decoder_parameters = {}

            decoder_dict = {"model": decoder_model,
                            "parameters": decoder_parameters}

            ranges_dict = {"label": label,
                           "code": code_dict,
                           "noise": noise_dict,
                           "decoder": decoder_dict,
                           "probability": [p]}

            json_dict = {"comments": "",
                         "ranges": ranges_dict}

            filename = os.path.join(input_dir, f'{label}.json')
            with open(filename, 'w') as json_file:
                json.dump(json_dict, json_file, indent=4)


@click.group(invoke_without_command=True)
@click.pass_context
def slurm(ctx):
    """Routines for generating and running slurm scripts."""
    if not ctx.invoked_subcommand:
        print(ctx.get_help())


@click.command()
@click.option('--n_trials', default=1000, type=click.INT, show_default=True)
@click.option('--partition', default='defq', show_default=True)
@click.option('--time', default='10:00:00', show_default=True)
@click.option('--cores', default=1, type=click.INT, show_default=True)
def gen(n_trials, partition, time, cores):
    """Generate sbatch files."""
    generate_sbatch(n_trials, partition, time, cores)


@click.command()
@click.argument('name', required=True)
@click.option('--n_trials', default=1000, type=click.INT, show_default=True)
@click.option('--nodes', default=1, type=click.INT, show_default=True)
@click.option('--ntasks', default=1, type=click.INT, show_default=True)
@click.option('--cpus_per_task', default=40, type=click.INT, show_default=True)
@click.option('--mem', default=10000, type=click.INT, show_default=True)
@click.option('--time', default='10:00:00', show_default=True)
@click.option('--split', default=1, type=click.INT, show_default=True)
@click.option('--partition', default='pml', show_default=True)
@click.option(
    '--cluster', default='nist', show_default=True,
    type=click.Choice(['nist', 'symmetry'])
)
def gennist(
    name, n_trials, nodes, ntasks, cpus_per_task, mem, time, split, partition,
    cluster
):
    """Generate sbatch files for NIST cluster."""
    generate_sbatch_nist(
        name, n_trials, nodes, ntasks, cpus_per_task, mem, time, split,
        partition, cluster
    )


@click.command()
@click.argument('folder', required=True, type=click.Choice(
    ['all', 'out', 'sbatch'],
    case_sensitive=False
))
def clear(folder):
    """Clear generated files."""
    if folder == 'out' or folder == 'all':
        clear_out_folder()
    if folder == 'sbatch' or folder == 'all':
        clear_sbatch_folder()


@click.command()
@click.argument('name', required=True)
def count(name):
    """Count number of input parameters contained."""
    n_runs = count_input_runs(name)
    print(n_runs)


@click.command()
def status():
    """Show the status of running jobs."""
    get_status()


slurm.add_command(gen)
slurm.add_command(gennist)
slurm.add_command(status)
slurm.add_command(count)
slurm.add_command(clear)
cli.add_command(run)
cli.add_command(ls)
cli.add_command(slurm)
cli.add_command(generate_input)
