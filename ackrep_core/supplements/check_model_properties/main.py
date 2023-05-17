import os
import time
import datetime as dt
from ackrep_core import models, core
import sys
from importlib import reload
from ipydex import IPS, activate_ips_on_exception
from ackrep_core.supplements.check_model_properties.properties import *

activate_ips_on_exception()

t = time.time()

result_list = []
entity_list = list(models.SystemModel.objects.all())
report = "Results"

test_list = [locally_strongly_accessible, exact_input_state_linearization]

# text file
timestamp = dt.datetime.now().strftime("__%Y_%m_%d__%H_%M_%S")
report_name = "report" + timestamp + ".txt"
filepath = os.path.join(os.path.split(os.path.abspath(__file__))[0], report_name)

for e in entity_list:
    key = e.key

    # only check double crane model:
    # if key != "IMLSG":
    #     continue

    # get path of the model
    cwd = os.getcwd()
    main_directory = os.path.split(cwd)[0]
    model_path = os.path.join(main_directory, e.base_path)
    # get model
    sys.path.append(model_path)

    try:
        system_model = reload(system_model)
    except NameError:
        import system_model

    model = system_model.Model()
    sys.path.remove(model_path)

    for f in test_list:
        t0 = time.time()
        try:
            flag, msg = f(model)
        except TimeoutException:
            flag, msg = [None, "timeout"]
        deltat = time.time() - t0
        result_data = [key, e.name, f.__name__, str(flag), str(round(deltat, 3)), msg]
        result_list.append(result_data)

        print(result_data)

        with open(filepath, "a") as f:
            f.write(", ".join([str(i) for i in result_data]) + "\n")


# total time in minutes
t_total = (time.time() - t) / 60
with open(filepath, "a") as f:
    f.write("\ntotal time: " + str(round(t_total, 2)) + " minutes")


