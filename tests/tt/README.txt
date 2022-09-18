How to regression test.

The .json files contain the json for the simulated API call.
The .yaml files contain the yaml to create the sensors for the corresponding .json file
The -dump.txt files contain the expected output from the sensor dump.
The automations.yaml file contains an automation that can be manually triggered to dump the sensor data.

Copy the desired .json file to /share/tt/test.json
Insert the corresponding .yaml file into Home Assistant's configuration.yaml file to create the test sensors.
Create an automation to dump the test sensors based on the automations.yaml file.
Restart HA.
Manually trigger the automation to create the sensor dump.
Compare to the expected results dump.
