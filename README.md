# Real-Time ESP32 Web Monitoring

Real-time IoT telemetry and remote monitoring platform using ESP32, MQTT, Node.js, Docker, and MySQL.

## Overview

This project was developed to demonstrate a complete IoT monitoring architecture capable of collecting, transmitting, storing, and visualizing real-time sensor data from an ESP32 device to a dedicated web server.

The system is designed with scalability and modularity in mind, combining embedded systems, backend development, networking, and data visualization technologies.

## Features

- Real-time sensor monitoring
- ESP32 Wi-Fi communication
- MQTT-based telemetry
- REST API integration
- Data storage using MySQL
- Web dashboard for live visualization
- Remote access through a dedicated Linux server
- Dockerized backend services
- Scalable IoT architecture

## System Architecture

````
+------------------+
|      ESP32       |
| Sensors & Data   |
+--------+---------+
         |
         | Wi-Fi / MQTT
         |
+--------v---------+
|   MQTT Broker    |
+--------+---------+
         |
         |
+--------v---------+
|  Node.js Backend |
|   REST API       |
+--------+---------+
         |
         |
+--------v---------+
|      MySQL       |
|   Data Storage   |
+--------+---------+
         |
         |
+--------v---------+
| Web Dashboard    |
| Real-Time Charts |
+------------------+
