from app import app, socketio
from flask import render_template, request, url_for
import time
from dronekit import connect, VehicleMode, LocationGlobalRelative
import dronekit_sitl
from app import celery
from requests import post
from flask_socketio import emit
import threading

SITL = 'tcp:127.0.0.1:5760'


@celery.task
def send_live_gps(sid, gps_url, drone):
    i = 0
    while i < 10:
        post(gps_url, json={
             'gps': drone.location.global_frame.alt, 'sid': sid})
        i += 1
        time.sleep(1)


@celery.task
def deploy_drone_async(latitude, longitude, sid, status_url, gps_url, ip_addr):
    def notify(msg):
        post(status_url, json={'status': msg, 'sid': sid})

    def arm_and_takeoff(altitude):
        notify("Basic pre-arm checks")
        # Don't try to arm until autopilot is ready
        while not drone.is_armable:
            notify(" Waiting for vehicle to initialise...")
            time.sleep(1)

        notify("Arming motors")
        # Copter should arm in GUIDED mode
        drone.mode = VehicleMode("GUIDED")
        drone.armed = True

        # Confirm drone armed before attempting to take off
        while not drone.armed:
            notify(" Waiting for arming...")
            time.sleep(1)

        notify("Taking off!")
        drone.simple_takeoff(altitude)  # Take off to target altitude

        # Wait until the vehicle reaches a safe height before processing the goto
        #  (otherwise the command after Vehicle.simple_takeoff will execute
        #   immediately).
        while True:
            notify(f"Altitude: {drone.location.global_relative_frame.alt}")
            # Break and return from function just below target altitude.
            if drone.location.global_relative_frame.alt >= altitude * 0.95:
                notify("Reached target altitude")
                break
            time.sleep(1)

    notify(f'Connecting to vehicle on: {ip_addr}')
    drone = connect(ip_addr, wait_ready=True)
    send_live_gps.apply_async(args=[sid, gps_url, drone], serializer="pickle")

    arm_and_takeoff(10)
    notify("Set default/target airspeed to 3")
    drone.airspeed = 3

    notify("Going towards first point for 30 seconds ...")
    point1 = LocationGlobalRelative(latitude, longitude, 20)
    drone.simple_goto(point1)

    # sleep so we can see the change in map
    time.sleep(30)

    notify("Returning to Launch")
    drone.mode = VehicleMode("RTL")

    # Close vehicle object before exiting script
    notify("Close vehicle object")
    drone.close()


@socketio.on('deploy_drone')
def deploy_drone(gps):
    assert gps.get('latitude') and gps.get('longitude')

    deploy_drone_async.delay(
        gps['latitude'], gps['longitude'],
        request.sid, url_for('status', _external=True), url_for('gps', _external=True), SITL)


@app.route('/status', methods=['POST'])
def status():
    sid = request.json['sid']
    status = request.json['status']
    emit('drone_status', status, room=sid, namespace='/')
    return 'OK'


@app.route('/gps', methods=['POST'])
def gps():
    sid = request.json['sid']
    gps = request.json['gps']
    emit('live_gps', gps, room=sid, namespace='/')
    return 'OK'


@app.route('/')
def index():
    return render_template('index.html')
