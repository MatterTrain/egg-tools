import base64
import ei_pb2
import json
import requests
from google.protobuf import json_format

user_id = "EIXXXXXX"
username = "XXXXXX"
fetch = False


class FirstContactData():
    def __init__(self, user_id, username="", fetch=True):
        self.user_id = user_id
        self.data = ei_pb2.EggIncFirstContactResponse()

        if fetch:
            self.__fetch_FirstContactResponse()
            self.username = self.data.backup.user_name

            json_string = json_format.MessageToJson(self.data)
            json_string = json_string[0:json_string.index("backup")+15] \
                + json_string[json_string.index("artifactsDb")-1:json_string.index("\"gameServicesId")-6] \
                + json_string[-6:]

            json_string = json_string[0:json_string.index(
                "\"itemSequence")-8] + json_string[-12:]

            self.data = ei_pb2.EggIncFirstContactResponse()
            json_format.Parse(json_string, self.data)
        else:
            self.username = username
            self.__load_FirstContactResponse()

    def __fetch_FirstContactResponse(self):
        first_contact_request = ei_pb2.EggIncFirstContactRequest()
        first_contact_request.ei_user_id = self.user_id
        first_contact_request.client_version: 50

        url = "https://ctx-dot-auxbrainhome.appspot.com/ei/bot_first_contact"
        data = {"data": base64.b64encode(
            first_contact_request.SerializeToString()).decode("utf-8")}
        response = requests.post(url, data=data)

        self.data.ParseFromString(base64.b64decode(response.text))

    def __load_FirstContactResponse(self):
        json_file = json.load(
            open(f"../artifact-data/FirstContactResponse_{self.username}.json", "r"))
        json_format.Parse(json.dumps(json_file), self.data)

    def download_FirstContactResponse(self):
        with open(f"../artifact-data/FirstContactResponse_{self.username}.json", "w") as json_file:
            json_file.write(json_format.MessageToJson(self.data))


if __name__ == "__main__":
    fcd = FirstContactData(user_id=user_id, username=username, fetch=fetch)
    fcd.download_FirstContactResponse()

    print(fcd.data.backup.artifacts_db.inventory_items)
