import requests
import urllib3
import json
import datetime
import re

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


class LiveFeed():
    """Class responsible for for interacting with the QLive API to pull questions and answers. """

    def __init__(self):
        self.bearer_token = "Bearer [insert bearer token here]"
        self.headers = {"Host": "api.uk.theq.live",
                        "Accept": "application/json",
                        "Accept-Language": "en-GB;q=1.0",
                        "Connection": "keep-alive",
                        "Accept-Encoding": "gzip;q=1.0, compress;q=0.5",
                        "User-Agent": "Q Live/1.4.1 (uk.co.q-live; build:1; iOS 10.2.0) Alamofire/4.7.3"
                        }
        self.body_pattern = re.compile(r"event: (.+?)\nid: ([0-9]+?)\ndata: (.+?)\n")
        self.consumed_ids = []

    def get_next_game(self):
        payload = {"includeSubscriberOnly": "1", "types": "TRIVIA,POPULAR"}
        uid = "[uid here]"
        payload.update({"uid": uid, "userId": uid})
        r = requests.get("https://api.uk.theq.live/v2/games", verify=False, params=payload, headers=self.headers)
        d = {}
        if r.status_code == 200:
            obj = json.loads(r.content.decode())
            ids = []
            times = []
            types = []
            hosts = []
            try:
                l = obj.get("games")
                for el in l:
                    id = el.get("id")
                    ids.append(id)
                    time_epoch = el.get("scheduled")
                    ts = datetime.datetime.fromtimestamp(time_epoch / 1000).strftime('%d-%m-%Y %H:%M:%S')
                    times.append(time_epoch)
                    theme = el.get("theme")
                    if theme:
                        type = theme.get("displayName")
                    else:
                        type = ""
                    types.append(type)
                    host = el.get("host")
                    if host:
                        hosts.append(host)
                    else:
                        pass
                    print(f"{id} - {ts}")
                d.update({"ids": ids, "times": times, "types": types, "hosts": hosts})
            except Exception as e:
                print(f"LiveFeed: Exception {e.msg}")
            return d

    def get_stream(self, id, queue=None, host="api-prod--002.uk.theq.live"):
        url = f"https://{host}/v2/event-feed/games/{id}"
        h = self.headers.copy()
        h.update({"User-Agent": "Q%20Live/1 CFNetwork/808.2.16 Darwin/16.3.0", "Accept": "*/*",
                  "Accept-Encoding": "gzip, deflate",
                  "Authorization": self.bearer_token})
        body_string = ""
        with requests.get(url, headers=h, verify=False, stream=True) as r:
            for chunk in r.iter_content(chunk_size=1):
                if chunk:
                    try:
                        body_string += chunk.decode()
                        if chunk.decode() == "\n":  # only worth reading when a newline is created
                            self.read_body_string(body_string, queue=queue)
                    except Exception as e:
                        print(f"LiveFeed: decode excetion {e}")
                    # print(body_string)
        return body_string

    def read_body_string(self, body_string, queue=None):
        body_string = "\n".join([line.strip() for line in body_string.split("\n")])  # strip each line
        results = re.findall(self.body_pattern, body_string)
        for result in results:
            if result[1] not in self.consumed_ids:
                if result[0] == "QuestionStart":
                    answers = []
                    obj = json.loads(result[2])
                    question = obj.get("question")
                    choices = obj.get("choices")
                    for choice in choices:
                        answer_id = choice.get("id")
                        answer = choice.get("choice")
                        answers.append(answer)
                    if queue:
                        queue.put({"question": question, "answers": answers, "data_obj": obj})
                    print(f"{question}: {str(answers)}")
                if result[0] == "GameEnded":
                    print("Game appears to be over")
                if result[0] == "QuestionResult":
                    obj = json.loads(result[2])
                    choices = obj.get("choices")
                    question_ID = None
                    choice_ID = None
                    choice_human_string = None
                    for choice in choices:
                        try:
                            if choice.get("correct"):
                                question_ID = choice.get("questionId")
                                choice_ID = choice.get("id")
                                choice_human_string = choice.get("choice")
                                break
                        except Exception as e:
                            print(f"failed as {e}")
                    if queue and question_ID and choice_ID and choice_human_string:
                        queue.put({"question_ID": question_ID, "choice_ID": choice_ID,
                                   "choice_human_string": choice_human_string})
                self.consumed_ids.append(result[1])
