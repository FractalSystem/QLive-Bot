import requests
import json
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class VirtualPlayer():
    """ Represents a single player in the game. Multiple instances of this object are managed by PlayerManager. """

    def __init__(self, gameID, authToken, uid, userID, desc, host="api-prod--002.uk.theq.live"):
        self.gameID = gameID
        self.authToken = authToken
        self.uid = uid
        self.userID = userID
        self.isAlive = True
        self.desc = desc
        h = self.get_host(uid)
        if h == -1:
            print(f"VirtualPlayer: {desc} got no host, defaulting to {host}")
            self.host = host
        else:
            print(f"VirtualPlayer: {desc} got host {h}")
            self.host = h
        self.is_eliminated = False
        self.choices = []  # list of {question_ID: "", choice_ID: ""}

    def get_host(self, uid):
        headers = {"Host": "api.uk.theq.live",
                   "Accept": "application/json",
                   "Accept-Language": "en-GB;q=1.0",
                   "Connection": "keep-alive",
                   "Accept-Encoding": "gzip;q=1.0, compress;q=0.5",
                   "User-Agent": "Q Live/1.4.1 (uk.co.q-live; build:1; iOS 10.2.0) Alamofire/4.7.3"
                   }
        payload = {"includeSubscriberOnly": "1", "types": "TRIVIA,POPULAR"}
        payload.update({"uid": uid, "userId": uid})
        r = requests.get("https://api.uk.theq.live/v2/games", verify=False, params=payload, headers=headers)
        if r.status_code == 200:
            obj = json.loads(r.content.decode())
            try:
                l = obj.get("games")
                for el in l:
                    host = el.get("host")
                    if host:
                        return host
                    else:
                        pass
            except Exception as e:
                print(f"VirtualPlayer: get_host failed with error: {e}")
            return -1

    def submit_answer(self, questionID, choiceID):
        # submits a desired answer regardless of whether the player is alive or dead
        success = False
        self.choices.append({"choice_ID": choiceID, "question_ID": questionID})
        print(f"VirtualPlayer: submitting answer as {self.desc}")
        try:
            url = f"https://{self.host}/v2/games/{self.gameID}/questions/{questionID}/responses"
            params = {"choiceId": choiceID}
            form = {"uid": self.uid, "userId": self.userID}
            headers = {"Host": self.host,
                       "Content-Type": "application/x-www-form-urlencoded; charset=utf-8",
                       "Connection": "keep-alive",
                       "Accept": "application/json",
                       "User-Agent": "Q Live/1.4.1 (uk.co.q-live; build:1; iOS 10.2.0) Alamofire/4.7.3",
                       "Authorization": self.authToken,
                       "Accept-Encoding": "gzip;q=1.0, compress;q=0.5",
                       "Accept-Language": "en-GB;q=1.0"}

            r = requests.post(url, params=params, data=form, headers=headers, verify=False)
            response_obj = json.loads(r.content.decode())
            success = response_obj.get("success")
            errorCode = response_obj.get("errorCode")
            if not success:
                if errorCode:
                    print(f"VirtualPlayer: {self.desc} success returned false with error \"{errorCode}\"")
                else:
                    print(f"VirtualPlayer: {self.desc} success returned false")
                self.isAlive = False
        except Exception as e:
            print(f"VirtualPlayer: submit_answer for {self.uid} failed. Maybe retry?")

        return success
