import os
import time
import sys
import logging as lg
from packaging import version
import datetime as dt
from ackrep_core import models, core
import yaml

from importlib import reload
from ipydex import IPS, activate_ips_on_exception
from ackrep_core.supplements.check_model_properties.properties import *
import symbtools as st


logger = lg.getLogger("ackrep-check-model-props")
logger.info("started")

st_version = version.parse(st.__version__)
if st_version >= version.parse("0.3.4"):
    logger.warning("The version of symbtools is unexpectedly low. Continuing anyway.")

activate_ips_on_exception()

t = time.time()

result_list = []
entity_list = list(models.SystemModel.objects.all())
report = "Results"

test_list = [LocalStrongAccess, ExactInputStateLinearization]

# text file
timestamp = dt.datetime.now().strftime("__%Y_%m_%d__%H_%M_%S")
report_name = "report" + timestamp + ".txt"
yaml_name = "report" + timestamp + ".yml"
filepath = os.path.join(os.path.split(os.path.abspath(__file__))[0], report_name)
yamlpath = os.path.join(os.path.split(os.path.abspath(__file__))[0], yaml_name)


ackrep_core_path = core.settings.BASE_DIR

# go one level up; this is the root of _data, _core, _deployment, etc
ackrep_project_path = os.path.dirname(ackrep_core_path)
result_dict = {}


for e in entity_list:
    key = e.key

    # useful for debugging
    # only check double crane model:
    if key != "XHINE":
        print(f"{e.key=}, {e.name=}")
        continue

    # get path of the model
    cwd = os.getcwd()
    model_path = os.path.join(ackrep_project_path, e.base_path)

    # get model
    sys.path.append(model_path)

    try:
        system_model = reload(system_model)
    except NameError:
        import system_model

    model = system_model.Model()
    sys.path.remove(model_path)

    for prop_class in test_list:
        prop = prop_class()
        t0 = time.time()
        try:
            flag, msg = prop.check_property(model)
        except TimeoutException:
            flag, msg = [None, "timeout"]
        deltat = time.time() - t0
        result_data = [key, e.name, prop.__name__, str(flag), str(round(deltat, 3)), msg]
        result_list.append(result_data)

        # now add data to dictionary for automated metadata completion
        if key not in result_dict.keys():
            result_dict[key] = {}
        result_dict[key][prop.erk_key] = {"result": flag, "duration": round(deltat, 3), "message": msg}


        logger.info(result_data)

        with open(filepath, "a") as f:
            f.write(", ".join([str(i) for i in result_data]) + "\n")
    break

# total time in minutes
t_total = (time.time() - t) / 60
with open(filepath, "a") as f:
    f.write("\ntotal time: " + str(round(t_total, 2)) + " minutes")

with open(yamlpath, "a") as f:
    yaml.dump(result_dict, f)

