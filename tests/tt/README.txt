How to regression test.

Use test_event.py to validate that sensor is returning the expected results across all supported sports and game situations.

The all.json file contains the json response for the simulated API call for the TEST_DATA sensors defined in const.py.
The expected result for each sensor defined in TEST_DATA is in the results directory.
The test_event.py file will test each sensor in the TEST_DATA and confirm it matches the expected result in the directory.
The test will fail if there are differences.
If the expected results are supposed to be different, the expected results file should be updated so the test will pass.
The expected results files can be updated manually.
The expected results files can also be regenerated in the /share/tt/results directory
  Add the yaml to your config to create the sensor.
  Copy the all.json file to /share/tt/test.yaml
  Create an empty /share/tt/results directory
  Restart HA
  The integrationw will create a new version of the expected results file.  Compare to prior version to ensure no unexpected changes were introduce.
  Update the expected results in the test/results directory.

Use test_multigame.py to validate the sensor pulls the correct competition to test situations like doubleheaders in baseball.

The multigame.json file contains the json response for the simulated API call for the MULTIGAME_DATA sensors defined in const.py.
The test_multigame.py file will test each sensor in MULTIGAME_DATA and confirm it matches expected results.
The test will fail if the sensor returns the wrong competition.
The test only validates if the right competition is returned.  It does not do the deep compare of each value as the prior test does. 

Legacy tests

The additional files are legacy manual tests that can be run for even deeper tests of specific sports if desired.

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
