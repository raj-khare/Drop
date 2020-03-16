from app import app, socketio
from flask import render_template, request
import time
from dronekit import connect, VehicleMode, LocationGlobalRelative, LocationGlobal
import dronekit_sitl
from flask_socketio import emit
from threading import Thread

SITL = 'tcp:127.0.0.1:5760'


class Drone(object):
    def __init__(self, vehicle, sid):
        self.gps_lock = False
        self.altitude = 10.0
        self.sid = sid

        # Connect to the Vehicle
        self._log('Connected to vehicle.')
        self.vehicle = vehicle
        self.vehicle.airspeed = 10000
        self.commands = self.vehicle.commands
        self.current_coords = []
        self._log("DroneDelivery Start")

        # Register observers
        self.vehicle.add_attribute_listener('location', self.location_callback)

    def launch(self):
        self._log("Waiting for location...")
        while self.vehicle.location.global_frame.lat == 0:
            time.sleep(0.1)
        self.home_coords = [self.vehicle.location.global_frame.lat,
                            self.vehicle.location.global_frame.lon]

        self._log("Waiting for ability to arm...")
        while not self.vehicle.is_armable:
            time.sleep(.1)

        self._log('Running initial boot sequence')
        self.change_mode('GUIDED')
        self.arm()
        self.takeoff()
        time.sleep(30)

    def takeoff(self):
        self._log("Taking off")
        self.vehicle.simple_takeoff(30.0)

    def arm(self, value=True):
        if value:
            self._log('Waiting for arming...')
            self.vehicle.armed = True
            while not self.vehicle.armed:
                time.sleep(.1)
        else:
            self._log("Disarming!")
            self.vehicle.armed = False

    def change_mode(self, mode):
        self._log("Changing to mode: {0}".format(mode))

        self.vehicle.mode = VehicleMode(mode)
        while self.vehicle.mode.name != mode:
            self._log('  ... polled mode: {0}'.format(mode))
            time.sleep(1)

    def goto(self, location, relative=None):
        self._log("Goto: {0}, {1}".format(location, self.altitude))

        if relative:
            self.vehicle.simple_goto(
                LocationGlobalRelative(
                    float(location[0]), float(location[1]),
                    float(self.altitude)
                )
            )
        else:
            self.vehicle.simple_goto(
                LocationGlobal(
                    float(location[0]), float(location[1]),
                    float(self.altitude)
                )
            )
        self.vehicle.flush()

    def get_location(self):
        return [self.current_location.lat, self.current_location.lon]

    def location_callback(self, vehicle, name, location):
        if location.global_relative_frame.alt is not None:
            self.altitude = location.global_relative_frame.alt

        self.current_location = location.global_relative_frame
        with app.app_context():
            emit('live_gps', {'lat': self.current_location.lat, 'lon': self.current_location.lon},
                 room=self.sid, namespace='/')

    def _log(self, message):
        with app.app_context():
            emit('drone_status', message, room=self.sid, namespace='/')


def deploy_drone_async(drone, user_lat, user_lon, sid):

    drone.launch()
    drone.goto((user_lat, user_lon), True)


@socketio.on('deploy_drone')
def deploy_drone(gps):
    assert gps.get('latitude') and gps.get('longitude')
    _drone = connect(SITL, wait_ready=True)
    drone = Drone(_drone, request.sid)

    deployment_thread = Thread(target=deploy_drone_async, args=(
        drone, gps['latitude'], gps['longitude'], request.sid))
    deployment_thread.daemon = True
    deployment_thread.start()


@app.route('/')
def index():
    return render_template('index.html')
