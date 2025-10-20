Project 108: Mobile Autonomous Buoy
Connor Dunn & Cromwell Pilacan

Low-cost autonomous surface vehicle (ASV) developed for inland water-quality monitoring. 
The system integrates 
	- ArduPilot Firmware
	- Raspberry Pi Companion 
	- ESP32 Power Controller
Planned but not implemented is
	- Custom power distribution PCB (made)
	- Solar power
	- Sonar

Folder Structure
108_cdun954_cpil673-compendium
├── Companion Pi
│   ├── Algorithm 	(test scripts)
│   ├── Camera 	(test scripts)
│   ├── MAVLink 	(test scripts)
│   ├── MQTT 		(test scripts)
│   └── src
│   │   ├── algo_test.py
│   │   ├── camera.py
│   │   ├── grid.py
│   │   ├── main.py
│   │   ├── mav.py
│   │   └── taka_lake.fen
│   └── boot_script.service
│
├── Diagrams
│   ├── coverage_algorithm.drawio
│   ├── high_level_system.drawio
│   ├── mounting.drawio
│   └── power_esp32.drawio
│
├── Flight Controller
│   ├── Logs/
│   │   ├── field_speed.BIN
│   │   ├── field_square.BIN
│   │   ├── sim_coverage.BIN
│   │   └── sim_square.BIN
│   ├── Sonar/
│   │   ├── sonar_dpt/sonar_dpt.ino
│   │   └── sonar_mav/sonar_mav.ino
│   └── params.param
│
├── GUI
│   ├── graph.py
│   ├── gui.py
│   └── gui.ui
│
├── Hardware
│   └── PCB/
│       └── (schematics and libraries)
│
├── Power Controller
│   ├── main/main.ino
│   ├── mavlink_test/mavlink_test.ino
│   └── mqtt_test/mqtt_test.ino
│
├── README.txt
└── setup.docx


Open setup.docx for setup and testing

Supervised by Dr. Akshat Bisht and Dr. Kevin I-Kai Wang
Department of Electrical, Computer, and Software Engineering, University of Auckland.