from datetime import date
from google.appengine.ext import ndb
import json
import webapp2


class Boat(ndb.Model):
    # TODO: Define a human-friendly alphanumeric ID scheme, if time permits
    # id = ndb.StringProperty()
    name = ndb.StringProperty(required=True)
    type = ndb.StringProperty(required=True)
    length = ndb.IntegerProperty(required=True)
    at_sea = ndb.BooleanProperty(default=True)

    @classmethod
    def get_by_id(cls, boat_id):
        boat = ndb.Key(Boat, long(boat_id)).get()
        return boat

    def to_json_ready(self):
        boat_json_ready = dict(id=self.key.id(), name=self.name, type=self.type, length=self.length,
                               at_sea=self.at_sea, self="/boats/" + str(self.key.id()),
                               docked_url="/boats/" + str(self.key.id()) + "/docked")

        return boat_json_ready


class BoatListHandler(webapp2.RequestHandler):

    def get(self):

        boats = Boat.query().fetch(30)

        boats_json = []
        for boat in boats:
            boats_json.append(boat.to_json_ready())

        send_success(self.response, json.dumps(boats_json))

    def post(self):

        request_data = json.loads(self.request.body)

        # TODO: If possible, switch the auto-generated ID to a string ID that is generated here.

        # TODO: Not thread-safe!! But probably not an issue for this assignment.
        existing = Boat.query().filter(Boat.name == request_data["name"]).fetch(1)
        if existing:
            send_error(self.response, 400,
                       response_message_json("FAILURE", "Boat name should be unique: {}".format(request_data["name"])))
            return

        # Don't set at_sea: All newly created boats should start "At sea"
        boat = Boat(name=request_data["name"], type=request_data["type"], length=request_data["length"])
        boat.put()

        send_success(self.response, json.dumps(boat.to_json_ready()))


class BoatHandler(webapp2.RequestHandler):

    def get(self, boat_id):

        boat = Boat.get_by_id(boat_id)

        # FIXME: Error handling

        if not boat:
            send_error(self.response, 404)
            return

        send_success(self.response, json.dumps(boat.to_json_ready()))

    def delete(self, boat_id):

        boat_key = ndb.Key(Boat, long(boat_id))
        # DEBUG
        boat = boat_key.get()

        # FIXME: Error handling

        slip = Slip.find_slip_by_boat_id(boat_key.id())

        if slip:
            slip.current_boat = None
            slip.arrival_date = None

            departure = dict(departure_date=date.today().strftime("%m/%d/%Y"), departed_boat=boat_key.id())
            slip.departure_history.append(departure)

            slip.put()

        boat_key.delete()

        send_success(self.response, None)

    def patch(self, boat_id):

        boat = Boat.get_by_id(boat_id)

        request_data = json.loads(self.request.body)
        if "name" in request_data and request_data["name"]:
            boat.name = request_data["name"]
        if "type" in request_data and request_data["type"]:
            boat.type = request_data["type"]
        if "length" in request_data and request_data["length"]:
            boat.length = request_data["length"]

        if "at_sea" in request_data:
                send_error(self.response, 404,
                           response_message_json("FAILURE", "Use PATCH /boat/:id/dock to dock a boat."))
                return

        boat.put()

        send_success(self.response, json.dumps(boat.to_json_ready()))


class BoatDockedHandler(webapp2.RequestHandler):

    def patch(self, boat_id):

        boat_key = ndb.Key(Boat, long(boat_id))
        boat = boat_key.get()

        request_data = json.loads(self.request.body)

        if "slip_id" not in request_data:
            send_error(self.response, 400, response_message_json("FAILURE", "slip_id property missing. " 
                       "Provide empty slip_id to set a boat at sea, or DELETE to the same entity."))
            return

        if request_data["slip_id"] is None:
            # The boat is leaving a slip. Validate first.
            if boat.at_sea:
                send_error(self.response, 400, response_message_json("FAILURE", "The boat is already at sea."))
                return

            current_slip = Slip.find_slip_by_boat_id(long(boat_id))

            if not current_slip:
                send_error(self.response, 400, response_message_json("FAILURE", "The boat is not at sea and not docked."))
                return

            if "departure_date" in request_data and request_data["departure_date"]:
                departure_date = request_data["departure_date"]
            else:
                departure_date = date.today().strftime("%m/%d/%Y")

            departure = dict(departure_date=departure_date, departed_boat=boat_id)
            current_slip.departure_history.append(departure)

            current_slip.current_boat = None
            current_slip.arrival_date = None
            current_slip.put()

            boat.at_sea = True
            boat.put()

            send_success(self.response, json.dumps(boat.to_json_ready()))
            return

        slip = Slip.get_by_id(long(request_data["slip_id"]))

        if slip:
            # The boat is docking. Validate first.
            if not boat.at_sea:
                send_error(self.response, 400, response_message_json("FAILURE", "The boat is already docked."))
                return

            if slip.current_boat:
                send_error(self.response, 403, response_message_json("FAILURE", "The slip is already occupied."))
                return

            slip.current_boat = long(boat_id)

            if "arrival_date" in request_data and request_data["arrival_date"]:
                slip.arrival_date = request_data["arrival_date"]
            else:
                slip.arrival_date = date.today().strftime("%m/%d/%Y")

            slip.put()

            boat.at_sea = False
            boat.put()

            send_success(self.response, json.dumps(boat.to_json_ready()))
            return

        else:
            # Slip provided but not found.
            send_error(self.response, 400, response_message_json("FAILURE", "The given slip id cannot be found."))
            return


class Slip(ndb.Model):
    # TODO: Define a human-friendly alphanumeric ID scheme, if time permits
    # id = ndb.StringProperty()
    number = ndb.IntegerProperty(required=True)
    current_boat = ndb.IntegerProperty(indexed=True)
    arrival_date = ndb.StringProperty()
    departure_history = ndb.JsonProperty(repeated=True)

    @classmethod
    def get_by_id(cls, slip_id):
        slip = ndb.Key(Slip, long(slip_id)).get()
        return slip

    @classmethod
    def find_slip_by_boat_id(cls, boat_id):
        slip = cls.query().filter(cls.current_boat == boat_id).get()
        return slip

    def to_json_ready(self):
        slip_json_ready = dict(id=self.key.id(), number=self.number, current_boat=self.current_boat,
                               arrival_date=self.arrival_date, departure_history=self.departure_history,
                               self="/slips/" + str(self.key.id()), boat_url=None)
        if self.current_boat:
            slip_json_ready["boat_url"] = "/boats/" + str(self.current_boat)

        return slip_json_ready


class SlipListHandler(webapp2.RequestHandler):

    def get(self):

        slips = Slip.query().fetch(30)

        slips_json = []
        for slip in slips:
            slips_json.append(slip.to_json_ready())

        send_success(self.response, (json.dumps(slips_json)))

    def post(self):
        request_data = json.loads(self.request.body)

        # Don't set current_boat. "All newly created slips should be empty."
        slip = Slip(number=int(request_data["number"]))
        slip.put()

        send_success(self.response, json.dumps(slip.to_json_ready()))


class SlipHandler(webapp2.RequestHandler):

    def get(self, slip_id):

        slip = ndb.Key(Slip, long(slip_id)).get()

        # FIXME: Error handling

        if not slip:
            send_error(self.response, 404)
            return

        send_success(self.response, json.dumps(slip.to_json_ready()))

    def delete(self, slip_id):

        slip = Slip.get_by_id(long(slip_id))

        # FIXME: Error handling

        # If there's a boat in this slip, need to set it at sea
        if slip.current_boat:
            boat = Boat.get_by_id(slip.current_boat)
            boat.at_sea = True
            boat.put()

        slip.key.delete()

        send_success(self.response, None)

    def patch(self, slip_id):

        slip = Slip.get_by_id(long(slip_id))

        request_data = json.loads(self.request.body)

        if "number" in request_data and request_data["number"]:
            slip.number = request_data["number"]


        slip.put()

        send_success(self.response, json.dumps(slip.to_json_ready()))


def send_success(response, body):
    if body:
        response.status = 200
        response.charset = "utf-8"
        response.content_type = 'application/json'  # ; charset=utf-8'
        response.write(body)
    else:
        response.status = 204


def send_error(response, code, body=None):

    response.status = code
    if body:
        response.charset = "utf-8"
        response.content_type = 'application/json'  # ; charset=utf-8'
        response.write(body)


def response_message_json(status, message):
    return '{"status": "' + status + '", "message": "' + message + '"}'


# Patch for "PATCH", taken from the "GAE Demo" video from the course.
allowed_methods = webapp2.WSGIApplication.allowed_methods
new_allowed_methods = allowed_methods.union(('PATCH',))
webapp2.WSGIApplication.allowed_methods = new_allowed_methods

app = webapp2.WSGIApplication([
    ('/boats', BoatListHandler),
    ('/boats/(\d+)', BoatHandler),
    ('/boats/(\d+)/docked', BoatDockedHandler),
    ('/slips', SlipListHandler),
    ('/slips/(\d+)', SlipHandler),
], debug=True)
