# This code is part of KQCircuits
# Copyright (C) 2022 IQM Finland Oy
#
# This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public
# License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied
# warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along with this program. If not, see
# https://www.gnu.org/licenses/gpl-3.0.html.
#
# The software distribution should follow IQM trademark policy for open-source software
# (meetiqm.com/developers/osstmpolicy). IQM welcomes contributions to the code. Please see our contribution agreements
# for individuals (meetiqm.com/developers/clas/individual) and organizations (meetiqm.com/developers/clas/organization).


import os
import stat
from pathlib import Path
import json
from distutils.dir_util import copy_tree

from kqcircuits.simulations.export.util import export_layers
from kqcircuits.util.export_helper import write_commit_reference_file
from kqcircuits.defaults import ELMER_SCRIPTS_PATH, default_layers
from kqcircuits.simulations.simulation import Simulation
from kqcircuits.util.geometry_json_encoder import GeometryJsonEncoder

default_gmsh_params = {
    'default_mesh_size': 100,  # Default size to be used where not defined
    'signal_min_mesh_size': 100,  # Minimum mesh size near signal region curves
    'signal_max_mesh_size': 100,  # Maximum mesh size near signal region curves
    'signal_min_dist': 100,  # Mesh size will be the minimum size until this distance from the signal region curves
    'signal_max_dist': 100,  # Mesh size will grow from to the maximum size until this distance from the signal region
                             # curves
    'signal_sampling': None,  # Number of points used for sampling each signal region curve
    'ground_min_mesh_size': 100,  # Minimum mesh size near ground region curves
    'ground_max_mesh_size': 100,  # Maximum  mesh size near ground region curves
    'ground_min_dist': 100,  # Mesh size will be the minimum size until this distance from the ground region curves
    'ground_max_dist': 100,  # Mesh size will grow from to the maximum size until this distance from the ground region
                             # curves
    'ground_sampling': None,  # Number of points used for sampling each ground region curve
    'ground_grid_min_mesh_size': 100,  # Minimum mesh size near ground_grid region curves
    'ground_grid_max_mesh_size': 100,  # Maximum mesh size near ground_grid region curves
    'ground_grid_min_dist': 100,  # Mesh size will be the minimum size until this distance from the ground_grid region
                                  # curves
    'ground_grid_max_dist': 100,  # Mesh size will grow from to the maximum size until this distance from the ground_
                                  # grid region curves
    'ground_grid_sampling': None,  # Number of points used for sampling each ground_grid region curve
    'gap_min_mesh_size': 100,  # Minimum mesh size near gap region curves
    'gap_max_mesh_size': 100,  # Maximum mesh size near gap region curves
    'gap_min_dist': 100,  # Mesh size will be the minimum size until this distance from the gap region curves
    'gap_max_dist': 100,  # Mesh size will grow from to the maximum size until this distance from the gap region curves
    'gap_sampling': None,  # Number of points used for sampling each gap region curve
    'port_min_mesh_size': 100,  # Minimum mesh size near port region curves
    'port_max_mesh_size': 100,  # Maximum mesh size near port region curves
    'port_min_dist': 100,  # Mesh size will be the minimum size until this distance from the port region curves
    'port_max_dist': 100,  # Mesh size will grow from to the maximum size until this distance from the port region
                           # curves
    'port_sampling': None,  # Number of points used for sampling each port region curve
    'algorithm': 5,  # Gmsh meshing algorithm (default is 5)
    'gmsh_n_threads': 1,  # number of threads used in Gmsh meshing (default=1, -1 means all physical cores)
    'show': False,  # Show the mesh in Gmsh graphical interface after completing the mesh (for large meshes this can
                    # take a long time)
}

default_workflow = {
    'run_gmsh': True,  # Run Gmsh to generate mesh
    'run_elmergrid': True,  # Run ElmerGrid
    'run_elmer': True,  # Run Elmer simulation
    'run_paraview': False,  # Run Paraview. This is visual view of the results.
    'elmer_n_processes': 1  # number of processes used in Elmer simulation (default=1, -1 means all physical cores)
}


def copy_elmer_scripts_to_directory(path: Path):
    """
    Copies Elmer scripts into directory path.

    Args:
        path: Location where to copy scripts folder.
    """
    if path.exists() and path.is_dir():
        copy_tree(str(ELMER_SCRIPTS_PATH), str(path))


def export_elmer_json(simulation: Simulation, path: Path, tool='capacitance', gmsh_params=None, workflow=None):
    """
    Export Elmer simulation into json and gds files.

    Args:
        simulation: The simulation to be exported.
        path: Location where to write json.
        tool(str): Elmer tool used. Available: "capacitance" that computes the capacitance matrix (Default: capacitance)
        gmsh_params(dict): Parameters for Gmsh
        workflow(dict): Parameters for simulation workflow

    Returns:
         Path to exported json file.
    """
    if simulation is None or not isinstance(simulation, Simulation):
        raise ValueError("Cannot export without simulation")

    # select layers
    layers = ["b_simulation_signal",
              "b_simulation_ground",
              "b_simulation_gap",
              "b_ground_grid"]
    if simulation.wafer_stack_type == "multiface":
        layers += ["t_simulation_signal",
                   "t_simulation_ground",
                   "t_simulation_gap",
                   "t_ground_grid"]

    # collect data for .json file
    json_data = {
        'tool': tool,
        **simulation.get_simulation_data(),
        'layers': {r: default_layers[r] for r in layers},
        'gmsh_params': default_gmsh_params if gmsh_params is None else {**default_gmsh_params, **gmsh_params},
        'workflow': default_workflow if workflow is None else {**default_workflow, **workflow}
    }

    # write .json file
    json_filename = str(path.joinpath(simulation.name + '.json'))
    with open(json_filename, 'w') as fp:
        json.dump(json_data, fp, cls=GeometryJsonEncoder, indent=4)

    # write .gds file
    gds_filename = str(path.joinpath(simulation.name + '.gds'))
    export_layers(gds_filename, simulation.layout, [simulation.cell], output_format='GDS2',
                  layers={default_layers[r] for r in layers})

    return json_filename


def export_elmer_script(json_filenames, path: Path, workflow, file_prefix='simulation',
        script_file='scripts/run.py'):
    """
    Create script files for running one or more simulations.
    Create also a main script to launch all the simulations at once.

    Args:
        json_filenames: List of paths to json files to be included into the script.
        path: Location where to write the script file.
        workflow(dict): Parameters for simulation workflow
        file_prefix: Name of the script file to be created.
        script_file: Name of the script file to run.

    Returns:

        Path of exported main script file
    """
    if 'sbatch_parameters' in workflow:
        sbatch = True
        sbatch_parameters = workflow['sbatch_parameters']
        elmer_n_processes = sbatch_parameters['--ntasks']
    else:
        sbatch = False

    main_script_filename = str(path.joinpath(file_prefix + '.sh'))
    with open(main_script_filename, 'w') as main_file:
        script_filenames = []
        for i, json_filename in enumerate(json_filenames):
            with open(json_filename) as f:
                json_data = json.load(f)
                simulation_name = json_data['parameters']['name']
            script_filename = str(path.joinpath(simulation_name + '.sh'))
            script_filenames.append(script_filename)
            with open(script_filename, 'w') as file:
                if sbatch:
                    file.write('#!/bin/bash\n')
                    file.write('#SBATCH --job-name={}_{}\n'.format(sbatch_parameters['--job-name'], str(i)))
                    file.write('#SBATCH --account={}\n'.format(sbatch_parameters['--account']))
                    file.write('#SBATCH --partition={}\n'.format(sbatch_parameters['--partition']))
                    file.write('#SBATCH --time={}\n'.format(sbatch_parameters['--time']))
                    file.write('#SBATCH --ntasks={}\n'.format(elmer_n_processes))
                    file.write('#SBATCH --cpus-per-task={}\n'.format(sbatch_parameters['--cpus-per-task']))
                    file.write('#SBATCH --mem-per-cpu={}\n'.format(sbatch_parameters['--mem-per-cpu']))
                    file.write('\n')
                    file.write('# set the number of threads based on --cpus-per-task\n')
                    file.write('export OMP_NUM_THREADS=$SLURM_CPUS_PER_TASK\n')
                    file.write('\n')
                    file.write('echo "Simulation {}/{} Gmsh"\n'.format(i + 1, len(json_filenames)))
                    file.write('srun -n 1 python {0} {1} --only-gmsh -q 2>&1 >> {1}_Gmsh.log\n'.format(
                        script_file,
                        Path(json_filename).relative_to(path))
                        )
                    file.write('echo "Simulation {}/{} ElmerGrid"\n'.format(i + 1, len(json_filenames)))
                    file.write('ElmerGrid 14 2 {0} 2>&1 >> {1}_ElmerGrid.log\n'.format(
                        simulation_name + ".msh",
                        Path(json_filename).relative_to(path))
                    )
                    file.write('ElmerGrid 2 2 {0} 2>&1 -metis {1} 4 --partdual --removeunused >> '\
                            '{2}_ElmerGrid_part.log\n'.format(
                        simulation_name,
                        str(elmer_n_processes),
                        Path(json_filename).relative_to(path))
                    )

                    file.write('echo "Simulation {}/{} Elmer"\n'.format(i + 1, len(json_filenames)))
                    file.write('srun --cpu-bind none -n {} ElmerSolver_mpi sif/{}.sif 2>&1 >> '\
                            '{}_Elmer.log\n'.format(
                                elmer_n_processes,
                                simulation_name,
                                Path(json_filename).relative_to(path)
                                ))
                    file.write('echo "Simulation {}/{} write results json"\n'.format(i + 1, len(json_filenames)))
                    file.write('srun -n 1 python {0} {1} --write-project-results 2>&1 >> '\
                            '{1}_write_project_results.log\n'.format(
                        script_file,
                        Path(json_filename).relative_to(path))
                    )
                else:
                    file.write('echo "Simulation {}/{} Gmsh"\n'.format(i + 1, len(json_filenames)))
                    file.write('python {0} {1} --only-gmsh 2>&1 >> {1}_Gmsh.log\n'.format(
                        script_file,
                        Path(json_filename).relative_to(path))
                    )
                    file.write('echo "Simulation {}/{} ElmerGrid"\n'.format(i + 1, len(json_filenames)))
                    file.write('python {0} {1} --only-elmergrid 2>&1 >> {1}_ElmerGrid.log\n'.format(
                        script_file,
                        Path(json_filename).relative_to(path))
                    )
                    file.write('echo "Simulation {}/{} Elmer"\n'.format(i + 1, len(json_filenames)))
                    file.write('python {0} {1} --only-elmer 2>&1 >> {1}_Elmer.log\n'.format(
                        script_file,
                        Path(json_filename).relative_to(path))
                    )
                    file.write('echo "Simulation {}/{} Paraview"\n'.format(i + 1, len(json_filenames)))
                    file.write('python {} {} --only-paraview\n'.format(
                        script_file,
                        Path(json_filename).relative_to(path))
                    )

            # change permission
            os.chmod(script_filename, os.stat(script_filename).st_mode | stat.S_IEXEC)

            if sbatch:
                main_file.write('echo "Submitting the main script of simulation {}/{}"\n'
                        .format(i + 1, len(json_filenames)))
                main_file.write('echo "--------------------------------------------"\n')
                main_file.write('sbatch {}\n'.format(Path(script_filename).relative_to(path)))
            else:
                main_file.write('echo "Submitting the main script of simulation {}/{}"\n'
                        .format(i + 1, len(json_filenames)))
                main_file.write('echo "--------------------------------------------"\n')
                main_file.write('./{}\n'.format(Path(script_filename).relative_to(path)))


    # change permission
    os.chmod(main_script_filename, os.stat(main_script_filename).st_mode | stat.S_IEXEC)

    return main_script_filename


def export_elmer(simulations: [], path: Path, tool='capacitance', file_prefix='simulation',
                 script_file='scripts/run.py', gmsh_params=None, workflow=None):
    """
    Exports an elmer simulation model to the simulation path.

    Args:

        simulations(list(Simulation)): list of all the simulations
        path(Path): Location where to output the simulation model
        tool(str): Elmer tool used. Available: "capacitance" that computes the capacitance matrix (Default: capacitance)
        file_prefix: File prefix of the script file to be created.
        script_file: Name of the script file to run.
        gmsh_params(dict): Parameters for Gmsh
        workflow(dict): Parameters for simulation workflow

    Returns:

        Path to exported script file.
    """
    write_commit_reference_file(path)
    copy_elmer_scripts_to_directory(path)
    json_filenames = []
    for simulation in simulations:
        json_filenames.append(export_elmer_json(simulation, path, tool, gmsh_params, workflow))

    return export_elmer_script(json_filenames, path, workflow, file_prefix=file_prefix, script_file=script_file)
