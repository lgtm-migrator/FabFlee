# -*- coding: utf-8 -*-
#
# This source file is part of the FabSim software toolkit,
# which is 151distributed under the BSD 3-Clause license.
# Please refer to LICENSE for detailed information regarding the licensing.
#
# This file contains FabSim definitions specific to fabFlee.

try:
    from fabsim.base.fab import *
except ImportError:
    from base.fab import *

# Import V&V primitives.
try:
    import fabsim.VVP.vvp as vvp
except ImportError:
    import VVP.vvp as vvp

import glob
import csv
import os
import numpy as np
import pandas as pd
from shutil import copyfile, rmtree, move
# Add local script, blackbox and template path.
add_local_paths("FabFlee")

# Import conflicts


@task
@load_plugin_env_vars("FabFlee")
def get_flee_location():
    """
    Print the $flee_location env variable for the target machine.
    """
    update_environment()
    print(env.machine_name, env.flee_location)


@task
@load_plugin_env_vars("FabFlee")
def sync_flee():
    """
    Synchronize the Flee version, so that the remote machine has the latest
    version from localhost.
    """
    update_environment()
    flee_location_local = user_config["localhost"].get(
        "flee_location", user_config["default"].get("flee_location"))

    rsync_project(
        local_dir=flee_location_local + '/',
        remote_dir=env.flee_location
    )


@task
@load_plugin_env_vars("FabFlee")
def flee(config, simulation_period, **args):
    """ Submit a Flee job to the remote queue.
    The job results will be stored with a name pattern as
    defined in the environment,
    e.g. car-abcd1234-localhost-4
    config :
        config directory to use for the simulation script, e.g. config=car2014
    simulation_period : length of the simulation in days.
    Keyword arguments:
            cores : number of compute cores to request
            wall_time : wall-time job limit
            memory : memory per node
    """

    '''
    update_environment({"input_directory": "%s/config_files/%s/input_csv"
                        % (get_plugin_path("FabFlee"), config),
                        "validation_data_directory":
                        "%s/config_files/%s/source_data"
                        % (get_plugin_path("FabFlee"), config)})
    print_local_environment()
    '''
    update_environment(args, {"simulation_period": simulation_period})
    with_config(config)
    execute(put_configs, config)
    job(dict(script='flee', wall_time='0:15:0', memory='2G'), args)


@task
def flees(config, simulation_period, **args):
    # Save relevant arguments to a Python or numpy list.
    print(args)

    # Generate config directories, copying from the config provided,
    # and adding a different generated test.csv in each directory.
    # Run the flee() a number of times.


@task
@load_plugin_env_vars("FabFlee")
def flee_ensemble(config, simulation_period, script='flee', label="", **args):
    """
    Submits an ensemble of dummy jobs.
    One job is run for each file in <config_file_directory>/flee_test/SWEEP.
    """
    update_environment(args)
    with_config(config)
    path_to_config = find_config_file_path(config)
    print("local config file path at: %s" % path_to_config)
    sweep_dir = path_to_config + "/SWEEP"
    env.script = script
    env.input_name_in_config = 'flee.txt'
    env.simulation_period = simulation_period

    if hasattr(env, 'NoEnvScript'):
        del env['NoEnvScript']

    # Re-add support for labels, which are overwritten by runensemble.
    if len(label) > 0:
        print("adding label: ", label)
        env.job_name_template += "_{}".format(label)

    run_ensemble(config, sweep_dir, **args)


def load_module_from_path(moduleName, PATH_to_module):
    import importlib

    try:
        importlib.import_module(moduleName)
        print("module {} is already in the PYTHONPATH "
              "and correctly loaded ".format(moduleName)
              )
    except ModuleNotFoundError:
        # add module PATH to PYTHONPATH
        sys.path.insert(0, PATH_to_module)
        try:
            # check again to see if the input moduleName can be loaded from
            # PATH_to_module or not
            importlib.import_module(moduleName)
            print("module {} loaded correctly form {} ".format(
                moduleName, env.flare_location)
            )
        except ModuleNotFoundError:
            raise ValueError(
                "The input PATH = {} for {} is not VALID!".format(
                    env.flare_location, moduleName)
            )
            sys.exit()
    except Exception as exception:
        print('Error: ', exception)
        sys.exit()


@task
@load_plugin_env_vars("FabFlee")
def flare_local(config, simulation_period, out_dir="", file_suffix=""):
    """
    Run an instance of Flare on the local host.
    """

    load_module_from_path(
        moduleName="flare", PATH_to_module=env.flare_location
    )
    load_module_from_path(
        moduleName="flee", PATH_to_module=env.flee_location
    )

    if len(out_dir) == 0:
        out_dir = "{}_single".format(config)

    flare_out_dir = "{}/results-flare/{}".format(
        get_plugin_path("FabFlee"), out_dir
    )
    config_dir = "{}/config_files/{}".format(
        get_plugin_path("FabFlee"), config
    )

    local("mkdir -p {}/input_csv".format(flare_out_dir))

    # load run_flare function from script directory
    from .scripts.run_flare import run_flare

    run_flare(
        config_dir="{}/input_csv".format(config_dir),
        flare_out_dir="{}/input_csv/conflicts{}.csv".format(
            flare_out_dir, file_suffix),
        simulation_period=int(simulation_period),
        file_suffix=file_suffix
    )


@task
@load_plugin_env_vars("FabFlee")
def flare_ensemble(config, simulation_period, N, out_dir, file_suffix=""):
    """
    Run an ensemble of flare instances locally.
    config: configuration directory.
    simulation_period: simulation period in days.
    N: number of instances in ensemble.
    out_dir: base output subdirectory in flare-results.
    """
    for i in range(0, int(N)):
        instance_out_dir = "%s/%s" % (out_dir, i)
        flare_local(config, simulation_period,
                    instance_out_dir, file_suffix=file_suffix)


@task
@load_plugin_env_vars("FabFlee")
def couple_flare_to_flee(config, flare_out="flare-out-scratch"):
    """
    Converts Flare output and places it in a Flee input directory to create
    a configuration for an ensemble run.
    """
    with_config(config)
    config_dir = env.job_config_path_local
    local("rm -rf %s/SWEEP" % (config_dir))
    local("mkdir -p %s/SWEEP" % (config_dir))
    local("cp -r %s/results-flare/%s/* %s/SWEEP/"
          % (get_plugin_path("FabFlee"), flare_out, config_dir))


@task
@load_plugin_env_vars("FabFlee")
def flee_conflict_forecast(config, simulation_period, N, **args):
    """
    Run Flare ensemble, convert output to Flee ensemble input,
    run Flee ensemble.
    (visualize Flee output with uncertainty).
    """
    update_environment(args)

    local("rm -rf %s/results-flare/flare-out-scratch/*" %
          (get_plugin_path("FabFlee")))
    flare_ensemble(config, simulation_period, N, "flare-out-scratch")

    couple_flare_to_flee(config, flare_out="flare-out-scratch")

    # config_dir = "%s/config_files/%s" % (get_plugin_path("FabFlee"), config)
    # local("mkdir -p %s/SWEEP" % (config_dir))
    # local("cp -r %s/results-flare/flare-out-scratch/* %s/SWEEP/"
    # % (get_plugin_path("FabFlee"), config_dir))

    flee_ensemble(config, simulation_period, **args)


# Flee parallelisation tasks
@task
@load_plugin_env_vars("FabFlee")
def pflee(config, simulation_period, **args):
    """ Submit a Pflee job to the remote queue.
    The job results will be stored with a name pattern as defined
    in the environment, e.g. car-abcd1234-localhost-4
    config :
        config directory to use for the simulation script, e.g. config=car2014
    Keyword arguments:
            cores : number of compute cores to request
            wall_time : wall-time job limit
            memory : memory per node
    """
    '''
    update_environment({"input_directory": "%s/config_files/%s/input_csv"
                        % (get_plugin_path("FabFlee"), config),
                        "validation_data_directory":
                        "%s/config_files/%s/source_data"
                        % (get_plugin_path("FabFlee"), config)})
    print_local_environment()
    '''
    update_environment(args, {"simulation_period": simulation_period})
    with_config(config)
    execute(put_configs, config)
    job(dict(script='pflee', wall_time='0:15:0', memory='2G'), args)


@task
@load_plugin_env_vars("FabFlee")
def pflee_test(config, pmode="advanced", N="100000", **args):
    """
    Run a short parallel test with a particular config.
    """
    update_environment(args, {"simulation_period": 10,
                              "flee_parallel_mode": pmode,
                              "flee_num_agents": int(N)
                              }
                       )
    with_config(config)
    execute(put_configs, config)
    job(dict(script='pflee_test', wall_time='0:15:0', memory='2G'), args)


@task
@load_plugin_env_vars("FabFlee")
def pflee_pmode_compare(config, cores, N="100000", **args):
    """
    Run a short parallel test with a particular config. 60 min limit per run.
    """
    # maps to args in test_par.py
    for pmode in ["advanced", "classic", "adv-lolat", "cl-hilat"]:
        update_environment(args, {"simulation_period": 10,
                                  "flee_parallel_mode": pmode,
                                  "flee_num_agents": int(N)
                                  }
                           )
        with_config(config)
        execute(put_configs, config)
        job(dict(script='pflee_test', wall_time='1:00:0',
                 memory='2G', cores=cores, label=pmode), args)


@task
@load_plugin_env_vars("FabFlee")
def pflee_report(results_key):
    for item in glob.glob("{}/*{}*/perf.log".format(env.local_results,
                                                    results_key)):
        print(item)
        with open(item) as csvfile:
            perf = csv.reader(csvfile)
            for k, e in enumerate(perf):
                if k == 1:
                    print(float(e[1]))

    # local("grep main {}/{}/perf.log".format(env.local_results,results_key))


@task
@load_plugin_env_vars("FabFlee")
def pflee_ensemble(config, simulation_period, **args):
    flee_ensemble(config, simulation_period, script='pflee', **args)


# Coupling Flee and food security tasks
@task
@load_plugin_env_vars("FabFlee")
def food_flee(config, simulation_period, **args):
    """ Submit a Flee job to the remote queue.
    The job results will be stored with a name pattern as defined
    in the environment, e.g. car-abcd1234-localhost-4
    config :
        config directory to use for the simulation script, e.g. config=car2014
    Keyword arguments:
            cores : number of compute cores to request
            wall_time : wall-time job limit
            memory : memory per node
    """
    update_environment({"input_directory": "%s/config_files/%s/input_csv"
                        % (get_plugin_path("FabFlee"), config),
                        "validation_data_directory":
                        "%s/config_files/%s/source_data"
                        % (get_plugin_path("FabFlee"), config)})
    # print_local_environment()
    update_environment(args, {"simulation_period": simulation_period})
    with_config(config)
    execute(put_configs, config)
    job(dict(script='flee_food', wall_time='0:15:0', memory='2G'), args)


@task
@load_plugin_env_vars("FabFlee")
# Syntax: fab localhost compare_food:food_flee_conflict_name_localhost_16
def compare_food(output_dir_1=""):
    """
    Compare results of the food based simulation with the original
    flee results throughout the whole simulation.
    Syntax:
        fab localhost compare_food:food_flee_conflict_name_localhost_16
        **or any name the food directory you want to use has.
        Make sure that the non-food one exists as well.
    """
    local("mkdir -p %s/%s/comparison" % (env.results_path, output_dir_1))
    output_dir_2 = output_dir_1.partition("_")[2]
    local("python3 %s/compare.py %s/%s %s/%s"
          % (env.flee_location,
             env.results_path, output_dir_1,
             env.results_path, output_dir_2))


# Post-processing tasks
@task
@load_plugin_env_vars("FabFlee")
# Syntax: fab localhost
# plot_output:flee_conflict_name_localhost_16(,graphs_dir_name)
def plot_output(output_dir="", graphs_dir=""):
    """ Plot generated output results using plot-flee-output.py. """
    local("mkdir -p %s/%s/%s" % (env.local_results, output_dir, graphs_dir))

    # import plot_flee_output.py from env.flee_location
    # when we have pip flee installation option, this part should be changed
    for p in env.flee_location.split(":"):
        sys.path.insert(0, p)

    from flee.postprocessing.plot_flee_output import plot_flee_output
    plot_flee_output(
        os.path.join(env.local_results, output_dir),
        os.path.join(env.local_results, output_dir, graphs_dir)
    )
    '''
    local("python3 %s/plot-flee-output.py %s/%s %s/%s/%s"
          % (env.flee_location,
             env.local_results, output_dir,
             env.local_results, output_dir, graphs_dir))
    '''


@task
@load_plugin_env_vars("FabFlee")
# Syntax: fab localhost
# plot_forecast:flee_conflict_name_localhost_16(,graphs_dir_name)
def plot_forecast(output_dir="", region_names=""):
    """ Plot generated output results using plot-flee-forecast.py. """
    # import plot_flee_forecast.py from env.flee_location
    # when we have pip flee installation option, this part should be changed
    for p in env.flee_location.split(":"):
        sys.path.insert(0, p)
    from flee.postprocessing.plot_flee_forecast import plot_flee_forecast

    region_names = []
    if len(region_names) > 0:
        region_names = region_names.split(';')

    input_dir = os.path.join(env.local_results, output_dir)
    if len(region_names) == 0:
        # find all region names
        data_dir = os.path.join(input_dir, "RUNS")
        dir_names = os.listdir(data_dir)
        for dir_names in os.listdir(data_dir):
            region_name = dir_names.rsplit('_', 1)[0]
            if region_name not in region_names:
                region_names.append(region_name)
        region_names.sort()

    plot_flee_forecast(
        input_dir=input_dir,
        region_names=region_names
    )


@task
@load_plugin_env_vars("FabFlee")
def cflee(config, coupling_type="file", weather_coupling="False",
          num_instances="1", instance_cores="1",
          job_wall_time="00:12:00", ** args):
    """ Submit a cflee (coupling flee) job to the remote queue.
    The job results will be stored with a name pattern as defined
    Required Keyword arguments:
        config :
            config directory to use for the simulation script,
            e.g. config=mscalecity
        coupling_type :
            the coupling model, currently two models are implemented :
            (1) file couping, and (2) muscle3
            acceptable input set : file / muscle3
    Example:
        fabsim eagle_hidalgo cflee:ssudan-mscale-test,coupling_type=file,
        weather_coupling=False,num_instances=2,instance_cores=2,TestOnly=True

        fabsim eagle_hidalgo cflee:ssudan-mscale-test,coupling_type=muscle3,
        weather_coupling=False,num_instances=2,instance_cores=2,TestOnly=True

        fabsim eagle_hidalgo cflee:ssudan-mscale-test,coupling_type=file,
        weather_coupling=True,num_instances=10,instance_cores=4

    """
    update_environment(args, {"coupling_type": coupling_type.lower(),
                              "weather_coupling": weather_coupling.lower(),
                              "num_instances": num_instances,
                              "instance_cores": instance_cores,
                              "job_wall_time": job_wall_time
                              }
                       )

    env.cores = int(num_instances) * int(instance_cores) * 2
    env.py_pkg = ["qcg-pilotjob", "pandas", "seaborn", "matplotlib", "jinja2"]
    if coupling_type == "file":
        script = "flee_file_coupling"
    elif coupling_type == "muscle3":
        env.cores += 2
        script = "flee_muscle3_coupling"
        env.py_pkg.append("muscle3")

    label = "coupling_{}_weather_{}".format(
        coupling_type, weather_coupling.lower()
    )
    with_config(config)
    execute(put_configs, config)

    job(dict(script=script, memory="24G", label=label), args)


@task
@load_plugin_env_vars("FabFlee")
def cflee_ensemble(config, coupling_type="file", weather_coupling="False",
                   num_workers="1", worker_cores="1",
                   N="1", simulation_period="425",
                   job_wall_time="00:12:00", ** args):
    """
    Example:
        fab eagle_vecma cflee_ensemble:mscalecity,coupling_type=file,
        weather_coupling=True,num_workers=2,worker_cores=2,N=3,TestOnly=True

        fab eagle_vecma cflee_ensemble:mscalecity,coupling_type=file,
        weather_coupling=True,num_workers=10,worker_cores=4,N=3
    """
    update_environment(args, {"coupling_type": coupling_type,
                              "weather_coupling": weather_coupling.lower(),
                              "num_workers": num_workers,
                              "worker_cores": worker_cores,
                              "job_wall_time": job_wall_time,
                              "simulation_period": simulation_period
                              }
                       )
    env.cores = int(num_workers) * int(worker_cores) * 2

    if coupling_type == 'file':
        script = 'flee_file_coupling'
        label = 'file_coupling'
    elif coupling_type == 'muscle3':
        script = 'flee_muscle3_coupling'
        label = 'muscle3_coupling'
    with_config(config)

    # clean config SWEEP dir if exists
    config_sweep_dir = env.job_config_path_local + "/SWEEP"
    if os.path.exists(config_sweep_dir):
        rmtree(config_sweep_dir)

    # clean flare SWEEP dir if exists
    flare_sweep_dir = "%s/results-flare/%s" % (
        get_plugin_path("FabFlee"), "SWEEP")
    if os.path.exists(flare_sweep_dir):
        rmtree(flare_sweep_dir)

    # run flare
    for file_suffix in ['-0', '-1']:
        flare_ensemble(config, simulation_period=simulation_period,
                       N=N, out_dir="SWEEP", file_suffix=file_suffix)

    # move flare SWEEP dir to config folder
    move(flare_sweep_dir, config_sweep_dir)

    execute(put_configs, config)

    # submit ensambe jobs
    path_to_config = find_config_file_path(config)
    sweep_dir = path_to_config + "/SWEEP"
    env.script = script
    env.label = label
    run_ensemble(config, sweep_dir, **args)


@task
@load_plugin_env_vars("FabFlee")
def flee_and_plot(config, simulation_period, **args):
    """
    Runs Flee and plots the output in a graph subdir
    """
    # update_environment(args, {"simulation_period": simulation_period})
    env.simulation_settings = "simsetting.csv"
    flee(config, simulation_period, **args)
    plot_output("%s" % (env.job_name), "graph")


@task
@load_plugin_env_vars("FabFlee")
# Syntax: fab localhost
# plot_uq_output:flee_conflict_name_localhost_16(,graphs_dir_name)
def plot_uq_output(output_dir="", graphs_dir=""):
    """ Plot generated output results using plot-flee-output.py. """
    local("mkdir -p %s/%s/%s" % (env.local_results, output_dir, graphs_dir))

    # import plot_flee_uq_output.py from env.flee_location
    # when we have pip flee installation option, this part should be changed
    for p in env.flee_location.split(":"):
        sys.path.insert(0, p)

    from flee.postprocessing.plot_flee_uq_output import plot_flee_uq_output
    plot_flee_uq_output(
        os.path.join(env.local_results, output_dir),
        os.path.join(env.local_results, output_dir, graphs_dir)
    )
    '''
    local("python3 %s/plot-flee-uq-output.py %s/%s %s/%s/%s"
          % (env.flee_location,
             env.local_results, output_dir,
             env.local_results, output_dir, graphs_dir))
    '''

# Validation tasks


def vvp_validate_results(output_dir="", **kwargs):
    """ Extract validation results (no dependencies on FabSim env). """

    flee_location_local = user_config["localhost"].get(
        "flee_location", user_config["default"].get("flee_location"))

    local("export PYTHONPATH=%s:${PYTHONPATH}; export FLEE_TYPE_CHECK=False; python3 %s/flee/postprocessing/extract-validation-results.py %s "
          "> %s/validation_results.yml"
          % (flee_location_local, flee_location_local, output_dir, output_dir))

    with open("{}/validation_results.yml".format(output_dir), 'r') as val_yaml:
        validation_results = yaml.load(val_yaml, Loader=yaml.SafeLoader)

        # TODO: make a proper validation metric using a validation schema.
        # print(validation_results["totals"]["Error (rescaled)"])
        print("Validation {}: {}".format(output_dir.split("/")[-1],
                                         validation_results["totals"][
                                         "Error (rescaled)"]))
        return validation_results["totals"]["Error (rescaled)"]

    print("error: vvp_validate_results failed on {}".format(output_dir))
    return -1.0


@task
@load_plugin_env_vars("FabFlee")
def flee_MOO(config, simulation_period=60, cores=1, **args):
    """
    fabsim localhost flee_MOO:moo_f1_c1_t3
    """
    if not isinstance(cores, int):
        cores = int(cores)

    update_environment(
        args,
        {"cores": cores, "simulation_period": simulation_period}
    )

    if cores > 1:
        env.flee_mode = "parallel"
    else:
        env.flee_mode = "serial"
    # set env flag to clear the previous execution folder in case of exists
    env.prevent_results_overwrite = "delete"
    with_config(config)

    ###########################################################################
    # MOO_setting.yaml contains the required setting for executing MOO code,  #
    # so, to be available on the remote machine, we temporally copy           #
    # MOO_setting.yaml file to the target config folder in                    #
    # FabFLee/config_files directory.                                         #
    # later, after execute(put_configs,..), we delete it from config folder   #
    # --------------                                                          #
    # Note :                                                                  #
    #       Hamid: I think this is better solution instead of opening another #
    #       ssh connection to remote machine for transferring only            #
    #       a single file                                                     #
    ###########################################################################
    copyfile(
        src=os.path.join(get_plugin_path("FabFlee"), "MOO_setting.yaml"),
        dst=os.path.join(env.job_config_path_local, "MOO_setting.yaml")
    )
    execute(put_configs, config)
    # now, we delete MOO_setting.yaml file from local config folder in
    # FabFLee/config_files directory
    os.remove(os.path.join(env.job_config_path_local, "MOO_setting.yaml"))

    script = "moo_flee"
    job(dict(script=script))


@task
@load_plugin_env_vars("FabFlee")
# fab localhost
# flee_optmization:output_dir=conflict1_camp1_town3_pop20000_MaxMoveSpeed360_localhost_16
def flee_optmization(output_dir):
    """
    fab localhost flee_optmization:output_dir=<folder output name in results
                                                folder"

    """
    flee_location_local = env.flee_location
    print("flee_location_local = {}\n".format(flee_location_local))
    # find the agents.out files

    agents_out_files = glob.glob(
        "{}".format(
            os.path.join(env.local_results, output_dir, "agents.out.*")
        )
    )

    # import required optimization functions from
    # flee/postprocessing/optimization.py
    optimization_file_PATH = os.path.join(
        flee_location_local, "postprocessing", "optimization.py"
    )
    sys.path.append(flee_location_local)
    import flee.postprocessing.optimization as opt
    camp_name = "Z"
    # calculate Camp population, obj#2
    df = pd.read_csv(
        os.path.join(env.local_results, output_dir, "out.csv")
    )
    sim_camp_population = df["{} sim".format(camp_name)].iloc[-1]
    print("sim camp {} population = {}\n".format(
        camp_name, sim_camp_population)
    )

    # calculate camp capacity
    df = pd.read_csv(
        os.path.join(
            env.local_results, output_dir, "input_csv", "locations.csv"
        )
    )
    camp_population = df[df["#name"] == camp_name]["population"].values[0]
    print("max camp {} population = {}\n".format(
        camp_name, camp_population)
    )

    # calculate remain camp capacity , obj#3
    remain_camp_capacity = camp_population - sim_camp_population
    print("remain camp {} capacity = {}\n".format(
        camp_name, remain_camp_capacity)
    )

    # obj#1
    for filename in agents_out_files:
        avg_distance_travelled = opt.avg_distance(
            file_path=filename, camp_name=camp_name
        )
        print(
            "Input file {}\n\tavg distance travelled for agents "
            "to camp name {} = {}".format(
                os.path.basename(filename),
                camp_name,
                avg_distance_travelled
            )
        )


@task
@load_plugin_env_vars("FabFlee")
# Syntax: fabsim localhost
# validate_results:flee_conflict_name_localhost_16
def validate_results(output_dir):
    score = vvp_validate_results("{}/{}".format(env.local_results, output_dir))
    print("Validation {}: {}".format(output_dir.split[-1]), score)
    return score


def make_vvp_mean(np_array, **kwargs):
    mean_score = np.mean(np_array)
    print("Mean score: {}".format(mean_score))
    return mean_score


@task
@load_plugin_env_vars("FabFlee")
def validate_flee_output(results_dir):
    """
    Goes through all the output directories and calculates the validation
    scores.
    """
    vvp.ensemble_vvp("{}/{}/RUNS".format(env.local_results, results_dir),
                     vvp_validate_results,
                     make_vvp_mean)


@task
@load_plugin_env_vars("FabFlee")
def validate_flee(simulation_period=0, cores=4, skip_runs=False, label="",
                  AwarenessLevel=1, **args):
    """
    Runs all the validation test and returns all scores, as well as an average.
    """
    if len(label) > 0:
        print("adding label: ", label)
        env.job_name_template += "_{}".format(label)

    env.prevent_results_overwrite = "delete"

    mode = "serial"
    if int(cores) > 1:
        mode = "parallel"

    if not skip_runs:
        if mode.lower() == "parallel":
            pflee_ensemble("validation", simulation_period,
                           cores=cores, **args)
        else:
            flee_ensemble("validation", simulation_period, cores=1, **args)

    # if not run locally, wait for runs to complete
    update_environment()
    if env.host != "localhost":
        wait_complete("")
    if skip_runs:
        env.config = "validation"

    fetch_results()

    results_dir = template(env.job_name_template)
    validate_flee_output(results_dir)


@task
@load_plugin_env_vars("FabFlee")
# Syntax: fabsim localhost new_conflict:<config_name>
def new_conflict(config, **args):
    local(template("mkdir -p %s/config_files/%s"
                   % (get_plugin_path("FabFlee"), config)))

    local(template("mkdir -p %s/config_files/%s/input_csv"
                   % (get_plugin_path("FabFlee"), config)))

    local(template("mkdir -p %s/config_files/%s/source_data"
                   % (get_plugin_path("FabFlee"), config)))

    local(template("cp %s/flee/config_template/run.py \
        %s/config_files/%s")
          % (env.flee_location, get_plugin_path("FabFlee"), config))

    local(template("cp %s/flee/config_template/run_par.py \
        %s/config_files/%s")
          % (env.flee_location, get_plugin_path("FabFlee"), config))

    local(template("cp %s/flee/config_template/simsetting.csv \
        %s/config_files/%s")
          % (env.flee_location, get_plugin_path("FabFlee"), config))

    local(template("cp %s/flee/config_template/input_csv/conflict_period.csv "
                   "%s/config_files/%s/input_csv")
          % (env.flee_location, get_plugin_path("FabFlee"), config))

    local(template("cp %s/flee/config_template/input_csv/closures.csv "
                   "%s/config_files/%s/input_csv")
          % (env.flee_location, get_plugin_path("FabFlee"), config))

    local(template("cp %s/flee/config_template/input_csv/"
                   "registration_corrections.csv "
                   "%s/config_files/%s/input_csv")
          % (env.flee_location, get_plugin_path("FabFlee"), config))


# ACLED data extraction task
# Syntax: fabsim localhost
# process_acled:country,start_date=dd-mm-yyyy,filter=[earliest,fatalities]
@task
def process_acled(country, start_date, filter_opt, admin_level):
    """
    Process .csv files sourced from acleddata.com to a <locations.csv> format
    Syntax:
        fabsim localhost process_acled:
        country (e.g ssudan, mali),
        start_date - "dd-mm-yyyy (date to calculate conflict_date from),
        filter_opt:[earliest,fatalities]
        **earliest keeps the first occurence of each admin2,
        fatalities keeps admin2 with the highest fatalities.
        admin_level: is how high the admin level you want to apply the
        filter_opt to i.e location, admin2, admin1
    """
    from .scripts.acled2locations import acled2locations

    acled2locations(
        fab_flee_loc=get_plugin_path("FabFlee"),
        country=country,
        start_date=start_date,
        filter=filter_opt,
        admin_level=admin_level
    )

    # local("python3 %s/scripts/acled2locations.py %s %s %s %s %s"
    #       % (get_plugin_path("FabFlee"),
    #          get_plugin_path("FabFlee"),
    #          country,
    #          start_date,
    #          filter_opt,
    #          admin_level))


@task
# Syntax: fabsim localhost
# extract_conflict_file:<country_name>,simulation_period=<number>
def extract_conflict_file(config, simulation_period, **args):
    """
    Travels to the input_csv directory of a specific config and extracts
    a conflict progression CSV file from locations.csv.
    """
    # config_dir = "%s/config_files/%s" % (get_plugin_path("FabFlee"), config)
    # local("python3 %s/scripts/location2conflict.py %s \
    #         %s/input_csv/locations.csv %s/input_csv/conflicts.csv"
    #       % (get_plugin_path("FabFlee"),
    #          simulation_period,
    #          config_dir,
    #          config_dir))

    config_dir = os.path.join(
        get_plugin_path("FabFlee"), "config_files", config
    )
    from .scripts.location2conflict import location2conflict
    location2conflict(
        simulation_period=int(simulation_period),
        input_file=os.path.join(config_dir, "input_csv", "locations.csv"),
        output_file=os.path.join(config_dir, "input_csv", "conflicts.csv"),
    )


@task
@load_plugin_env_vars("FabFlee")
# Syntax: fabsim localhost add_population:<config_name>
def add_population(config, PL="100", CL="100", **args):
    # update_environment(args, {"simulation_period": simulation_period})
    with_config(config)
    if env.machine_name != 'localhost':
        print("Error : This task should only executed on your localhost")
        print("Please re-run is again with :")
        print("\t fab localhost add_population:%s" % (config))
        exit()
    env.cityGraph_POPULATION_LIMIT = PL
    env.cityGraph_CITIES_LIMIT = CL
    local("python %s --cityGraph_location %s --API_KEY %s "
          "--POPULATION_LIMIT %s --CITIES_LIMIT %s "
          "--config_location %s --config_name %s"
          % (os.path.join(env.localplugins["FabFlee"],
                          "scripts",
                          "population2locations.py"),
             env.cityGraph_location,
             env.cityGraph_API_KEY,
             env.cityGraph_POPULATION_LIMIT,
             env.cityGraph_CITIES_LIMIT,
             env.job_config_path_local,
             config
             )
          )

# FabFlee execution tasks


@task
def load_conflict(conflict_name):
    # Syntax: fab localhost load_conflict:conflict_name
    """
    Load source data and flee csv files for a specific conflict from
    conflict data to active conflict directory.
    """
    # copies *.csv files from $FabFlee/conflict_data/<conflict_name> to
    # $FabFlee/conflict_data/active_conflict.

    # 1. Load locations.csv, routes.csv and closures.csv files which
    # correspond to a specific conflict.
    # These CSV will be store in $FabFlee/conflict_data. Each conflict will be
    # stored in a separate folder.

    # 2. Move these CSVs to an "active_conflict" directory.
    # This is located in $FABSIM/conflict_data/active_conflict.
    local(template("mkdir -p %s/conflict_data/active_conflict"
                   % (get_plugin_path("FabFlee"))))

    local(template("cp %s/conflict_data/%s/*.csv \
        %s/conflict_data/active_conflict/")
          % (get_plugin_path("FabFlee"), conflict_name,
             get_plugin_path("FabFlee")))

    local(template("mkdir -p %s/conflict_data/active_conflict/source_data"
                   % (get_plugin_path("FabFlee"))))

    local(template("cp %s/conflict_data/%s/source_data/*.csv \
        %s/conflict_data/active_conflict/source_data/")
          % (get_plugin_path("FabFlee"), conflict_name,
             get_plugin_path("FabFlee")))

    local(template("cp %s/config_files/run.py \
        %s/conflict_data/active_conflict")
          % (get_plugin_path("FabFlee"), get_plugin_path("FabFlee")))

    with open("%s/conflict_data/active_conflict/commands.log.txt"
              % (get_plugin_path("FabFlee")), "a") as myfile:
        myfile.write("fab localhost load_conflict:%s\n" % conflict_name)


@task
def instantiate(conflict_name):
    # Syntax: fab localhost instantiate:conflict_name
    """
    Copy modified active conflict directory to config_files
    (i.e. flee_conflict_name) to run instance with Flee.
    """

    # 1. Copy modified active_conflict directory to instantiate runs with
    # specific conflict name
    local(template("mkdir -p %s/config_files/%s"
                   % (get_plugin_path("FabFlee"), conflict_name)))

    local(template("mkdir -p %s/config_files/%s/input_csv"
                   % (get_plugin_path("FabFlee"), conflict_name)))

    local(template("cp %s/conflict_data/active_conflict/*.csv \
        %s/config_files/%s/input_csv")
          % (get_plugin_path("FabFlee"), get_plugin_path("FabFlee"),
             conflict_name))

    local(template("cp %s/conflict_data/active_conflict/commands.log.txt \
        %s/config_files/%s/")
          % (get_plugin_path("FabFlee"), get_plugin_path("FabFlee"),
             conflict_name))

    local(template("mkdir -p %s/config_files/%s/source_data"
                   % (get_plugin_path("FabFlee"), conflict_name)))

    local(template("cp %s/conflict_data/active_conflict/source_data/*.csv \
        %s/config_files/%s/source_data")
          % (get_plugin_path("FabFlee"), get_plugin_path("FabFlee"),
             conflict_name))

    local(template("cp %s/conflict_data/active_conflict/run.py \
        %s/config_files/%s/run.py")
          % (get_plugin_path("FabFlee"), get_plugin_path("FabFlee"),
             conflict_name))

    local(template("cp %s/config_files/run_food.py \
        %s/config_files/%s/run_food.py")
          % (get_plugin_path("FabFlee"), get_plugin_path("FabFlee"),
             conflict_name))
    # line added to copy run_food.py as well (otherwise executing
    # food_flee doesn't work...)

    # line added to copy simsetting.csv and make sure that
    # flee.SimulationSettings....ReadfromCSV works.
    local(template("cp %s/config_files/simsetting.csv \
        %s/config_files/%s/simsetting.csv")
          % (get_plugin_path("FabFlee"), get_plugin_path("FabFlee"),
             conflict_name))


@task
def clear_active_conflict():     # Syntax: fab localhost clear_active_conflict
    """ Delete all content in the active conflict directory. """

    local(template("rm -rf %s/conflict_data/active_conflict/"
                   % (get_plugin_path("FabFlee"))))


# FabFlee refinement tasks
@task
# Syntax: fab localhost
# change_capacities:camp_name=capacity(,camp_name2=capacity2)
def change_capacities(**capacities):
    """
    Change the capacity of a set of camps in the active conflict directory.
    """
    # Note: **capacities will be a Python dict object.

    capacities_string = ""
    for c in capacities.keys():
        capacities_string += "%s=%s" % (c, capacities[c])
    with open("%s/conflict_data/active_conflict/commands.log.txt"
              % (get_plugin_path("FabFlee")), "a") as myfile:
        myfile.write("fab localhost change_capacities:%s\n"
                     % capacities_string)

    # 1. Read in locations.csv
    # 2. for each location in the dict, find it in the csv, and modify the
    # population value accordingly.
    import csv
    r = csv.reader(open("%s/conflict_data/active_conflict/locations.csv"
                        % (get_plugin_path("FabFlee"))))
    lines = [l for l in r]

    for camp_name in capacities.keys():
        for i in range(1, len(lines)):
            if lines[i][5].strip() != "camp":
                continue
            if lines[i][0].strip() != camp_name:
                continue

            lines[i][7] = capacities[camp_name]

            print(lines[i])

    # 3. Write the updated CSV file.
    writer = csv.writer(open("%s/conflict_data/active_conflict/locations.csv"
                             % (get_plugin_path("FabFlee")), "w"))
    writer.writerows(lines)


@task
def find_capacity(csv_name):
    # Syntax: fab localhost find_capacity:csv_name
    """
    Find the highest refugee number within csv file of source data
    for neighbouring camps.
    """

    import csv
    csv_file = open("%s/conflict_data/active_conflict/source_data/%s"
                    % (get_plugin_path("FabFlee"), csv_name)).readlines()
    print(max(((i, int(l.split(',')[1])) for i, l in enumerate(
        csv_file)), key=lambda t: t[1])[1])


@task
# Syntax: fab localhost add_camp:camp_name,region,country(,lat,lon)
def add_camp(camp_name, region=" ", country=" ", lat=0.0, lon=0.0):
    """ Add an additional new camp to locations.csv. """

    with open("%s/conflict_data/active_conflict/commands.log.txt"
              % (get_plugin_path("FabFlee")), "a") as myfile:
        myfile.write("fab localhost add_camp:%s\n" % camp_name)

    # 1. Add (or make existing forwarding hub) a new camp to locations.csv
    # If new camp, add country,lat,lon,location_type(camp)
    # If existing camp, change location_type to camp
    import csv
    r = csv.reader(open("%s/conflict_data/active_conflict/locations.csv"
                        % (get_plugin_path("FabFlee")), "r"))
    lines = [l for l in r]

    for i in range(1, len(lines)):
        if lines[i][0].strip() != camp_name:
            continue
        print("Warning: camp %s is already present in locations.csv."
              % (camp_name))
        return

    # 2. Append one line to lines, containing the details of the new camp.
    add_camp = [camp_name, region, country, lat, lon, "camp"]
    with open("%s/conflict_data/active_conflict/locations.csv"
              % (get_plugin_path("FabFlee")), "a") as new_csv:
        writer = csv.writer(new_csv)
        writer.writerow(add_camp)
    print(add_camp)


@task
def add_new_link(name1, name2, distance):
    """  Add a new link between locations to routes.csv. """
    with open("%s/conflict_data/active_conflict/commands.log.txt"
              % (get_plugin_path("FabFlee")), "a") as myfile:
        myfile.write("fab localhost add_new_link:%s,%s,%s\n"
                     % (name1, name2, distance))

    # 1. Read routes.csv and for each location in the dict, find in the csv,
    # and change distance between two locations.
    import csv
    r = csv.reader(open("%s/conflict_data/active_conflict/routes.csv"
                        % (get_plugin_path("FabFlee"))))
    lines = [l for l in r]

    for i in range(1, len(lines)):
        if lines[i][0].strip() != name1:
            continue
        if lines[i][1].strip() != name2:
            continue
        lines[i][2] = distance
        print(lines[i])

    # 2. Append one line to lines, containing the details of links.
    add_new_link = [name1, name2, distance]
    with open("%s/conflict_data/active_conflict/routes.csv"
              % (get_plugin_path("FabFlee")), "a") as new_csv:
        writer = csv.writer(new_csv)
        writer.writerow(add_new_link)
    print(add_new_link)


@task
# Syntax: fab localhost delete_location:location_name
def delete_location(location_name):
    """ Delete not required camp (or location) from locations.csv. """

    with open("%s/conflict_data/active_conflict/commands.log.txt"
              % (get_plugin_path("FabFlee")), "a") as myfile:
        myfile.write("fab localhost delete_location:%s\n" % location_name)

    # 1. Delete camp from locations.csv containing the details of the camp.
    # 2. Write the updated CSV file.
    import csv
    r = csv.reader(open("%s/conflict_data/active_conflict/locations.csv"
                        % (get_plugin_path("FabFlee")), "r"))
    lines = [l for l in r]

    writer = csv.writer(open("%s/conflict_data/active_conflict/locations.csv"
                             % (get_plugin_path("FabFlee")), "w"))

    for i in range(0, len(lines)):
        if lines[i][0].strip() != location_name:
            writer.writerow(lines[i])
            continue

            print(lines[i])

    # 3. Check whether wanted to delete camp is present in locations.csv
    for i in range(1, len(lines)):
        if lines[i][0] == location_name:
            continue
        print("Warning: camp %s is deleted from locations.csv."
              % (location_name))
        return


@task
# Syntax: fab localhost change_distance:name1,name2,distance
def change_distance(source, destination, distance):
    """ Change distance between two locations in routes.csv. """

    with open("%s/conflict_data/active_conflict/commands.log.txt"
              % (get_plugin_path("FabFlee")), "a") as myfile:
        myfile.write("fab localhost change_distance:%s,%s,%s\n"
                     % (source, destination, distance))

    # 1. Read routes.csv and for each location in the dict, find in the csv,
    # and change distance between two locations.
    import csv
    r = csv.reader(open("%s/conflict_data/active_conflict/routes.csv"
                        % (get_plugin_path("FabFlee"))))
    lines = [l for l in r]

    for i in range(1, len(lines)):
        if lines[i][0].strip() != source:
            continue
        if lines[i][1].strip() != destination:
            continue
        lines[i][2] = distance
        print(lines[i])

    # 2. Write the updated closures.csv in the active_conflict directory.
    writer = csv.writer(open("%s/conflict_data/active_conflict/routes.csv"
                             % (get_plugin_path("FabFlee")), "w"))
    writer.writerows(lines)


@task
# Syntax: fab localhost
# close_camp:camp_name,country(,closure_start,closure_end)
def close_camp(camp_name, country, closure_start=0, closure_end=-1):
    """ Close camp located within neighbouring country. """

    with open("%s/conflict_data/active_conflict/commands.log.txt"
              % (get_plugin_path("FabFlee")), "a") as myfile:
        myfile.write("fab localhost close_camp:%s,%s\n" % (camp_name, country))

    # 1. Change closure_start and closure_end or add a new
    # camp closure to closures.csv.
    # Format: closure type <location>,name1,name2,closure_start,closure_end
    import csv
    r = csv.reader(open("%s/conflict_data/active_conflict/closures.csv"
                        % (get_plugin_path("FabFlee"))))  # Here your csv file
    lines = [l for l in r]
    camp_found = False

    for i in range(1, len(lines)):
        if lines[i][0].strip() != "location":
            continue
        if lines[i][1].strip() != camp_name:
            continue
        if lines[i][2].strip() != country:
            continue
        lines[i][3] = closure_start
        lines[i][4] = closure_end
        camp_found = True
        print(lines[i])

    if not camp_found:
        lines.append(["location", camp_name, country,
                      closure_start, closure_end])
    # print(lines)

    # 2. Write the updated closures.csv in the active_conflict directory.
    writer = csv.writer(open("%s/conflict_data/active_conflict/closures.csv"
                             % (get_plugin_path("FabFlee")), "w"))
    writer.writerows(lines)


@task
# Syntax: fab localhost
# close_border:country1,country2(,closure_start,closure_end)
def close_border(country1, country2, closure_start=0, closure_end=-1):
    """
    Close border between conflict country and camps located
    within specific neighbouring country.
    """

    with open("%s/conflict_data/active_conflict/commands.log.txt"
              % (get_plugin_path("FabFlee")), "a") as myfile:
        myfile.write("fab localhost close_border:%s,%s\n"
                     % (country1, country2))

    # 1. Change closure_start and closure_end or add a new camp
    # closure to closures.csv.
    # Format: closure type <country>,name1,name2,closure_start,closure_end
    import csv
    r = csv.reader(open("%s/conflict_data/active_conflict/closures.csv"
                        % (get_plugin_path("FabFlee"))))
    lines = [l for l in r]
    border_found = False

    for i in range(1, len(lines)):
        if lines[i][0].strip() != "country":
            continue
        if lines[i][1].strip() != country1:
            continue
        if lines[i][2].strip() != country2:
            continue
        lines[i][3] = closure_start
        lines[i][4] = closure_end
        border_found = True
        print(lines[i])

    if not border_found:
        lines.append(["country", country1, country2,
                      closure_start, closure_end])

    '''
    local(template("cp %s/conflict_data/%s/*.csv \
        %s/conflict_data/active_conflict/")
          % (get_plugin_path("FabFlee"), conflict_name,
             get_plugin_path("FabFlee")))
    print(lines)
    '''

    # 2. Write the updated closures.csv in the active_conflict directory.
    writer = csv.writer(open("%s/conflict_data/active_conflict/closures.csv"
                             % (get_plugin_path("FabFlee")), "w"))
    writer.writerows(lines)


@task
def redirect(source, destination):
    # Syntax: fab localhost redirect:location_name1,location_name2
    """
    Redirect from town or (small/other)camp to (main)camp.
    """

    with open("%s/conflict_data/active_conflict/commands.log.txt"
              % (get_plugin_path("FabFlee")), "a") as myfile:
        myfile.write("fab localhost redirect:%s,%s\n" % (source, destination))

    # 1. Read locations.csv and for each location in the dict, find in the csv,
    # and redirect refugees from location in neighbouring country to camp.
    # 2. Change location_type of source location to forwarding_hub.
    import csv
    r = csv.reader(open("%s/conflict_data/active_conflict/locations.csv"
                        % (get_plugin_path("FabFlee"))))
    lines = [l for l in r]

    for i in range(1, len(lines)):
        if lines[i][0].strip() != source:
            continue
        lines[i][5] = "forwarding_hub"

        print(lines[i])

    # 3. Write the updated CSV file.
    writer = csv.writer(open("%s/conflict_data/active_conflict/locations.csv"
                             % (get_plugin_path("FabFlee")), "w"))
    writer.writerows(lines)

    # 4. Find the route from source to destination in routes.csv, and enable
    # forced_redirection.
    r = csv.reader(open("%s/conflict_data/active_conflict/routes.csv"
                        % (get_plugin_path("FabFlee"))))
    lines = [l for l in r]

    for i in range(1, len(lines)):
        if lines[i][0].strip() != source:
            continue
        if lines[i][1].strip() != destination:
            continue
        lines[i][3] = "2"
        print(lines[i])

    for i in range(1, len(lines)):
        if lines[i][0].strip() != destination:
            continue
        if lines[i][1].strip() != source:
            continue
        lines[i][3] = "1"
        print(lines[i])

    # 5. Write the updated CSV file.
    writer = csv.writer(open("%s/conflict_data/active_conflict/routes.csv"
                             % (get_plugin_path("FabFlee")), "w"))
    writer.writerows(lines)


# Test Functions
# from plugins.FabFlee.test_FabFlee import *

try:
    from plugins.FabFlee.run_simulation_sets import *
except:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print("Error: failed to import settings module run_simulation_sets")
    pprint(exc_type)
    pprint(exc_value)
    import traceback
    traceback.print_tb(exc_traceback)
    print("The FabFlee run_simulation_sets functionalities are not imported as a result.")
    pass

try:
    # loads Sensitivity analysis (SA) tasks
    from plugins.FabFlee.SA.flee_SA import flee_init_SA
    from plugins.FabFlee.SA.flee_SA import flee_analyse_SA
except:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print("Error: failed to import settings module flee_SA")
    pprint(exc_type)
    pprint(exc_value)
    import traceback
    traceback.print_tb(exc_traceback)
    print("The FabFlee flee_SA functionalities are not imported as a result.")
    pass

try:
    # # loads Validation and Verification Patterns (VVP) tasks
    from plugins.FabFlee.VVP.flee_vvp import flee_init_vvp_LoR
    from plugins.FabFlee.VVP.flee_vvp import flee_analyse_vvp_LoR

    from plugins.FabFlee.VVP.flee_vvp import flee_init_vvp_QoI
    from plugins.FabFlee.VVP.flee_vvp import flee_analyse_vvp_QoI
except:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print("Error: failed to import settings module flee_vvp")
    pprint(exc_type)
    pprint(exc_value)
    import traceback
    traceback.print_tb(exc_traceback)
    print("The FabFlee flee_vvp functionalities are not imported as a result.")
    pass

try:
    from plugins.FabFlee.run_perf_benchmarks import *
except:
    exc_type, exc_value, exc_traceback = sys.exc_info()
    print("Error: failed to import settings module run_perf_benchmarks")
    pprint(exc_type)
    pprint(exc_value)
    import traceback
    traceback.print_tb(exc_traceback)
    print("The FabFlee run_perf_benchmarks functionalities are not imported as a result.")
    pass
