import VirtualPlayer
import time
import threading

player_list = [{"uid": "[player uid here]", "authToken": "Bearer [bearer token here]", "desc": "[username here]"},
               {"uid": "[player uid here]", "authToken": "Bearer [bearer token here]", "desc": "[username here]"},
               {"uid": "[player uid here]", "authToken": "Bearer [bearer token here]", "desc": "[username here]"},
               {"uid": "[player uid here]", "authToken": "Bearer [bearer token here]", "desc": "[username here]"},
               {"uid": "[player uid here]", "authToken": "Bearer [bearer token here]", "desc": "[username here]"},
               {"uid": "[player uid here]", "authToken": "Bearer [bearer token here]", "desc": "[username here]"}]


class PlayerManager():
    """ Class responsible for managing multiple VirtualPlayers. Will keep track of alive and dead players, while also
    submitting responses to the API on their behalf. """

    def __init__(self, num_players, gameID, host="api-prod--002.uk.theq.live"):
        self.players = []
        # flag to allow user inputted answers from gui and interrupt countdown
        self.countdown_active = False
        if num_players > len(player_list):
            num_players = len(player_list)
        for i in range(num_players):
            print(f"PlayerManager: Creating player {player_list[i].get('desc')}")
            uid = player_list[i].get("uid")
            authToken = player_list[i].get("authToken")
            userID = uid
            desc = player_list[i].get("desc")
            self.players.append(VirtualPlayer.VirtualPlayer(gameID, authToken, uid, userID, desc, host))
        self.correct_answers = []  # list of {question_ID: "", choice_ID: ""}

    def append_correct_response(self, questionID, choiceID, choice_human_string):
        self.correct_answers.append({"choice_ID": choiceID, "question_ID": questionID})
        print(
            f"PlayerManager: appending correct answer {choice_human_string} with choice_ID:{choiceID}, and question ID {questionID}")
        self.check_if_players_eliminated()

    def check_if_players_eliminated(self):
        print("Checking whether players have been eliminated")
        alive_player_counter = 0
        for player in self.players:
            submitted_answers = player.choices
            if all(i in self.correct_answers for i in
                   submitted_answers):  # checks if lists are equal regardless of order
                print(f"Player {player.desc} is still in the game")
                alive_player_counter += 1
                player.is_eliminated = False
            else:
                # print(f"submitted: {submitted_answers}\nactual: {self.correct_answers}")
                print(f"Player {player.desc} appears to be eliminated")
                player.is_eliminated = True

        print(f"\n{'-'*20}\n{alive_player_counter}/{len(self.players)} players still alive \n{'-'*20}")

    def send_answers(self, questionID, choiceID):
        # could multithread this
        for player in self.players:
            print(f"Sending answer with choiceID {choiceID} as {player.desc}")
            player.submit_answer(questionID, choiceID)

    def send_answer(self, questionID, choiceID, player):
        # sends an answer for a single player
        # could multithread this
        print(f"Sending answer with choiceID \"{choiceID}\" as {player.desc}")
        player.submit_answer(questionID, choiceID)

    def get_winning_players(self):
        d = {}
        for i, player in enumerate(self.players):
            if player.isAlive:
                d.update({str(i): f"Auth: {player.authToken}, uid: {player.uid}"})
        print(d)
        return d

    def clear_dead_players(self):
        # this method might not be useful as we want highscore so keep submitting
        for player in self.players:
            if not player.isAlive:
                self.players.remove(player)
                print(f"PlayerManager: {player.desc} is dead, removing from players list")

    def question_start(self, score_obj):
        # signal question has started and start countdown
        self.countdown_active = True
        if score_obj.data_obj:
            print(f"PlayerManager: Question started. Beginning countdown")
            t = threading.Thread(target=(lambda: self.countdown_thread(score_obj)))
            t.start()
        else:
            print(f"PlayerManager: No data_obj in scorer. Can't start question")

    def countdown_thread(self, score_obj):
        self.countdown_active = True
        try:
            data_obj = score_obj.data_obj
            question_ID = data_obj.get("questionId")
            choices = data_obj.get("choices")
            t = data_obj.get("secondsToRespond")
            # t=1
            print(f"countdown_thread sleeping for {t}s")
            time.sleep(int(t))
            if self.countdown_active:
                print(
                    f"PlayerManager: Countdown finished and no answers manually submitted. Submitting answers automatically...")
                answers = score_obj.get_best_answers()
                print(answers)
                alive_players = []
                dead_players = []
                for i, player in enumerate(
                        self.players):  # Split into alive and dead to allow even distribution of live player's answers
                    if player.is_eliminated:
                        dead_players.append(player)
                    else:
                        alive_players.append(player)
                if len(answers) == 1:  # Just submit same answer for all players
                    choiceID = choices[answers[0]].get("id")
                    self.send_answers(question_ID, choiceID)
                elif len(answers) == 2:
                    # alternate between players sending answer (modulus % does this)
                    print(f"PlayerManager: submitting alive players' answers")
                    for i, player in enumerate(alive_players):
                        choiceID = choices[answers[i % 2]].get("id")
                        self.send_answer(question_ID, choiceID, player)
                    print(f"PlayerManager: submitting dead players' answers")
                    for i, player in enumerate(dead_players):
                        choiceID = choices[answers[i % 2]].get("id")
                        self.send_answer(question_ID, choiceID, player)
                elif len(answers) == 3:
                    # alternate between players sending answer (modulus % does this)
                    print(f"PlayerManager: submitting alive players' answers")
                    for i, player in enumerate(alive_players):
                        choiceID = choices[answers[i % 3]].get("id")
                        self.send_answer(question_ID, choiceID, player)
                    print(f"PlayerManager: submitting dead players' answers")
                    for i, player in enumerate(dead_players):
                        choiceID = choices[answers[i % 3]].get("id")
                        self.send_answer(question_ID, choiceID, player)
                else:
                    choiceID = choices[answers[0]].get("id")
                    self.send_answers(question_ID, choiceID)

                # self.clear_dead_players() We want players to keep submitting answers!
                # for player in self.players:
                #     print(f"PlayerManager: {player.desc} is alive.")

        except Exception as e:
            print(f"PlayerManager: Countdown_thread failed with exception {e.with_traceback()}")

    def manually_send_answers(self, score_obj, answer_num):
        try:
            data_obj = score_obj.data_obj
            question_ID = data_obj.get("questionId")
            choices = data_obj.get("choices")

            if answer_num == -1:
                alive_players = []
                dead_players = []
                for i, player in enumerate(
                        self.players):  # Split into alive and dead to allow even distribution of live players' answers
                    if player.is_eliminated:
                        dead_players.append(player)
                    else:
                        alive_players.append(player)
                print(f"PlayerManager: submitting alive players' answers")
                for i, player in enumerate(alive_players):
                    choiceID = choices[i % 3].get("id")
                    self.send_answer(question_ID, choiceID, player)
                print(f"PlayerManager: submitting dead players' answers")
                for i, player in enumerate(dead_players):
                    choiceID = choices[i % 3].get("id")
                    self.send_answer(question_ID, choiceID, player)
            else:
                choiceID = choices[answer_num].get("id")
                self.send_answers(question_ID, choiceID)
            self.countdown_active = False
            return True
        except Exception as e:
            print(f"PlayerManager: manual answer submission failed with error: {e}")
