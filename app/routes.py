from app import app, socketio
from flask import render_template, request, url_for
import time
from dronekit import connect, VehicleMode, LocationGlobalRelative
import dronekit_sitl
from app import celery
from requests import post
from flask_socketio import emit


@celery.task
def deploy_drone_async(sid, url):
    def notify(msg):
        post(url, json={'status': msg, 'sid': sid})

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

    sitl = dronekit_sitl.start_default()
    connection_string = sitl.connection_string()
    notify(f'Connecting to vehicle on: {connection_string}')
    drone = connect(connection_string, wait_ready=True)
    arm_and_takeoff(10)
    notify("Set default/target airspeed to 3")
    drone.airspeed = 3

    notify("Going towards first point for 30 seconds ...")
    point1 = LocationGlobalRelative(-35.361354, 149.165218, 20)
    drone.simple_goto(point1)

    # sleep so we can see the change in map
    time.sleep(30)

    notify("Returning to Launch")
    drone.mode = VehicleMode("RTL")

    # Close vehicle object before exiting script
    notify("Close vehicle object")
    drone.close()

    # Shut down simulator if it was started.
    if sitl:
        sitl.stop()


@socketio.on('deploy_drone')
def deploy_drone():
    task = deploy_drone_async.delay(
        request.sid, url_for('status', _external=True))


@app.route('/status', methods=['POST'])
def status():
    sid = request.json['sid']
    status = request.json['status']
    emit('drone_status', status, room=sid, namespace='/')
    return 'OK'


@app.route('/request', methods=['POST'])
def request_drone():
    latitude, longitude = request.form.get(
        'latitude', None), request.form.get('longitude', None)
    assert latitude and longitude
    return render_template('request.html', latitude=latitude, longitude=longitude)


@app.route('/')
def index():
    return render_template('index.html')
