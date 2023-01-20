import os
import time
from ackrep_core import models, core
import sys
from local_strong_access import locally_strongly_accessible
from importlib import reload

t = time.time()

access_list = []
entity_list = list(models.SystemModel.objects.all())
report = "Results"

for e in entity_list:
    key = e.key

    # get path of the model
    cwd = os.getcwd()
    main_directory = os.path.split(cwd)[0]
    model_path = main_directory + "\\" + e.base_path
    
    # get model
    sys.path.append(model_path)
    if e == entity_list[0]:
        import system_model
    else: 
        system_model = reload(system_model)
    model = system_model.Model()
    sys.path.remove(model_path)

    t0 = time.time()
    flag, msg = locally_strongly_accessible(model)                  # specify here which property you want to check
    deltat = time.time() - t0

    result_data = [key, e.name, str(flag), str(round(deltat, 3)), msg]
    access_list.append(result_data)

    data = ", ".join(result_data)
    report = report + " \n " + data

    print(result_data)

# total time in minutes
t_total = (time.time() - t) / 60                    
report = report + " \n \n total time: " + str(round(t_total,2)) + " minutes"

# text file
filepath = os.path.split(os.path.abspath(__file__))[0] + "\\report.txt"
f = open(filepath, "w")
f.write(report)