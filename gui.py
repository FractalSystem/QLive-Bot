from tkinter import *
import tkinter.font as tkFont
import tkinter.ttk as ttk
from ctypes import windll
import threading
from multiprocessing.dummy import Pool as ThreadPool
import time
import subprocess
import GoogleVisionAPI
import ScreenProcessor
from GoogleScrape import GoogleScrape
from AsyncSearcher import AsyncSearcher
from Scorer import Scorer
from MyUtilities import sanitise_text, time_in_range
import html
from PIL import Image, ImageTk
import webbrowser
import LiveFeed
import queue
import PlayerManager
import datetime

windll.shcore.SetProcessDpiAwareness(1)


class Main():
    """ Main entrypoint for the GUI. Class handles core logic and GUI elements. """

    def __init__(self):
        self.label = 0
        self.question_num = 1
        self.filename = "temp.png"
        self.updateloop = False
        self.DEBUG = False
        self.DEBUG_LIST = []
        self.queue = queue.Queue()
        self.player_manager = None
        self.gameType = None  # string describing if game is spelling or not
        self.table_built = False

    def search(self, question, answers, question_num, data_obj=None):
        """
        Takes question as string and answers as list of strings.
        performs forward search. This is a good place to put checks on question string
        """

        if " not " in question.lower():
            not_question = True
        else:
            not_question = False
        self.score_obj = Scorer(question, answers, not_question, question_num, self.mainlbl)
        if data_obj:
            self.score_obj.set_data_obj(data_obj)
            # signal all players that the question has started, we need a data object to initiate this properly
            if self.player_manager:
                self.player_manager.question_start(self.score_obj)

        if " not " in question.lower():
            not_question = True

        birth_keywords = [" born", " birth", "young"]  # "old" but don't want to interfere with date of death"
        if any(x in question.lower() for x in birth_keywords):
            self.dox_search("date of birth", "")
        death_keywords = ["die", "died", "death"]
        if any(x in question.lower() for x in death_keywords):
            self.dox_search("date of death", "")
        release_keywords = ["released", "written", "sung", "sang", "published", "written"]
        if any(x in question.lower() for x in release_keywords):
            self.dox_search("", "release date")

        self.forward_search(self.score_obj)

    def forward_search(self, score_obj):
        """
        Search by googling question and looking for answers in results
        """
        google_results = GoogleScrape().search(sanitise_text(score_obj.get_question()))
        score_obj.score_titles(google_results[1])
        score_obj.score_descriptions(google_results[2])
        score_obj.set_snippet(google_results[3])
        self.updateloop = True
        threading.Thread(target=(lambda: self.scoreUpdateLoop(score_obj))).start()
        AsyncSearcher(google_results, score_obj)
        self.updateloop = False
        self.mainlbl["bg"] = "lightgreen"

    def scoreUpdateLoop(self, score_obj):
        while True:
            scores = score_obj.get_scores()
            google_scores = score_obj.get_google_scores()
            answers = score_obj.get_answers()
            self.answer1scorelbl["text"] = f"{round(scores[0],1)} ({google_scores[0]})"
            self.answer2scorelbl["text"] = f"{round(scores[1],1)} ({google_scores[1]})"
            self.answer3scorelbl["text"] = f"{round(scores[2],1)} ({google_scores[2]})"
            key_sentences = score_obj.get_key_sentences()
            s = ""
            for key in key_sentences:
                list_string = ""
                for el in key_sentences[key]:
                    list_string += el
                s += (f"{key.title()}: {list_string}") + "\n\n"
            self.keySentenceslbl["text"] = s

            self.answer1whichlbl["text"] = "| " + html.unescape(score_obj.get_which_results()[0])
            self.answer2whichlbl["text"] = "| " + html.unescape(score_obj.get_which_results()[1])
            self.answer3whichlbl["text"] = "| " + html.unescape(score_obj.get_which_results()[2])
            self.googleSentenceslbl["text"] = score_obj.get_snippet()
            table = score_obj.get_table()
            if table and not self.table_built:
                self.build_table(table)
                self.table_built = True
            if self.module1Active:
                s = ""
                for i in range(len(self.module1Results)):
                    s += f"{answers[i]}: {self.module1Results[i]}\n"
                self.module1lbl["text"] = s

            else:
                self.module1lbl["text"] = ""
            if self.updateloop == False:
                break
            time.sleep(0.5)

    def build_table(self, table):
        max_col_width = 200
        headers = table.get("headers")[0]
        # print(f"Headers: {headers}")
        rows = table.get("rows")
        # print(f"Rows: {rows}")
        self.tree["columns"] = headers  # name the columns
        for col in headers:
            self.tree.heading(col, text=col.title(),
                              command=lambda c=col: self.sort_table(self.tree, c, 0))  # add command for sort
            self.tree.column(col, width=tkFont.Font().measure(col.title()))

        for row in rows:
            self.tree.insert('', 'end', values=row)
            for i, val in enumerate(row):
                col_width = tkFont.Font().measure(val)
                if col_width < max_col_width:
                    if self.tree.column(headers[i], width=None) < col_width:
                        self.tree.column(headers[i], width=col_width)
                else:
                    self.tree.column(headers[i], width=max_col_width)
            # ignored scaling here from example https://www.daniweb.com/programming/software-development/threads/350266/creating-table-in-python

    def sort_table(self, tree, col, descending):
        data = [(tree.set(child, col), child) for child in tree.get_children('')]
        data.sort(reverse=descending)
        for ix, item in enumerate(data):
            tree.move(item[1], '', ix)
        # switch the heading so it will sort in the opposite direction
        tree.heading(col, command=lambda col=col: self.sort_table(tree, col, int(not descending)))

    def show_image(self, filename):
        pil_img = Image.open(self.filename)
        [imageSizeWidth, imageSizeHeight] = pil_img.size
        scaling_factor = 0.35
        newImageSizeWidth = int(imageSizeWidth * scaling_factor)
        newImageSizeHeight = int(imageSizeHeight * scaling_factor)
        pil_img = pil_img.resize((newImageSizeWidth, newImageSizeHeight), Image.ANTIALIAS)
        self.img = ImageTk.PhotoImage(pil_img)
        width = self.imglbl.winfo_width()
        height = self.imglbl.winfo_height()
        self.imglbl.create_image(width / 2, height / 2, anchor=CENTER, image=self.img)

    def run_vision_api_thread(self):
        self.adb_screencap(self.filename)
        self.show_image(self.filename)
        img_annotations = GoogleVisionAPI.image_to_tags(self.filename)
        self.imgtextlbl["text"] = img_annotations
        self.infolbl["text"] = "Ready."

    def trait_search(self, input_list):
        # input_list = [query, prestring, poststring, index_to_return]
        if len(input_list) == 4:
            if input_list[3] == -1:
                return GoogleScrape().search(f"{input_list[1]} {input_list[0]} {input_list[2]}", number_of_results=10)
            else:
                return GoogleScrape().search(f"{input_list[1]} {input_list[0]} {input_list[2]}", number_of_results=1)[
                    input_list[3]]
        else:
            return GoogleScrape().search(f"{input_list[1]} {input_list[0]} {input_list[2]}", number_of_results=1)[4]

    def run_spellchecker(self, question=None, answers=None, data_obj=None):
        self.clear_all_text()
        if question and answers:
            print(f"gui: SpellChecker: We have question and answers")
            # all good, we have question and answers
        else:
            self.adb_screencap(self.filename)
            question, answers = ScreenProcessor.process_file(self.filename)

        self.score_obj = Scorer(question, answers, False, None, self.mainlbl)  # untested 22/03/19 to allow answer input
        if data_obj:
            self.score_obj.set_data_obj(data_obj)
        # question = " ..  ."
        # answers = ["a: massachusetts", "b: massachusettss", "0: mssachusetts"]
        self.answer1lbl["text"] = answers[0] + ": "
        self.answer2lbl["text"] = answers[1] + ": "
        self.answer3lbl["text"] = answers[2] + ": "
        in_list = []
        for answer in answers:
            index = answer.find(":")
            in_list.append([answer[index + 1:].strip(), "define", "", -1])
        pool = ThreadPool(3)
        pool_results = pool.map(self.trait_search, in_list)
        pool.close()
        pool.join()
        scores = [0, 0, 0]
        for result in pool_results:
            for i, answer in enumerate(answers):
                for title in result[1]:  # titles
                    if title.lower().find(
                            answer[answer.find(':') + 1:].strip().lower() + " ") != -1 or title.lower().find(
                        " " + answer[answer.find(':') + 1:].strip().lower()) != -1:
                        scores[i] += 1
                        # print(f"True {answer}, {title}")
                for desc in result[2]:  # descriptions
                    if desc.lower().find(
                            answer[answer.find(':') + 1:].strip().lower() + " ") != -1 or desc.lower().find(
                        " " + answer[answer.find(':') + 1:].strip().lower()) != -1:
                        scores[i] += 1
                        # print("added")
                    else:
                        pass
        try:
            self.answer1whichlbl["text"] = scores[0]
            self.answer2whichlbl["text"] = scores[1]
            self.answer3whichlbl["text"] = scores[2]

        except IndexError:
            self.infolbl["text"] = "Spell checking module: list out of bound. This shouldn't happen"
            print("Spell checking module: list out of bound. This shouldn't happen")
            return
        self.infolbl["text"] = "Ready."

    def dox_search(self, pre, post):
        def internal_thread(pre, post, score_obj):
            in_list = []
            prestring = pre
            poststring = post
            for answer in score_obj.get_answers():
                in_list.append([answer, prestring, poststring])
                # score google results
            pool = ThreadPool(3)
            self.module1Results = pool.map(self.trait_search, in_list)
            self.module1Active = True
            pool.close()
            pool.join()
            self.scoreUpdateLoop(self.score_obj)

        self.infolbl["text"] = f"Running {pre} {post} search..."
        threading.Thread(target=(lambda: internal_thread(pre, post, self.score_obj))).start()

    def keyEvent(self, event):
        def internal_thread(pool):
            pool.close()
            pool.join()
            self.scoreUpdateLoop(self.score_obj)
            print("Deactivated module 1")

        try:
            if event.char == 'o':  # showImg
                threading.Thread(target=self.show_image, args=(self.filename,)).start()
            if event.char == "i":  # visionAPI
                self.infolbl["text"] = "Running Vision API..."
                threading.Thread(target=self.run_vision_api_thread).start()
            if event.char == "c":  # clear canvas
                self.imglbl.delete("all")
                self.imgtextlbl["text"] = " "
            if event.char == "b":  # dob
                self.dox_search("date of birth", "")
            if event.char == "r":
                self.dox_search("", "release date")
            if event.char == "d":
                self.dox_search("date of death", "")
            if event.char == "s":  # check spelling
                self.infolbl["text"] = "Running spell check module..."
                threading.Thread(target=(lambda: self.run_spellchecker())).start()
            if event.char == "l":
                url = "https://www.google.co.uk/maps/dir/" + "/".join(answer for answer in self.score_obj.get_answers())
                print(url)
                webbrowser.open(url)

            if event.char == "1":  # one, not 'l'
                self.player_manager.manually_send_answers(self.score_obj, 0)
            if event.char == "2":  # one, not 'l'
                self.player_manager.manually_send_answers(self.score_obj, 1)
            if event.char == "3":  # one, not 'l'
                self.player_manager.manually_send_answers(self.score_obj, 2)
            if event.char == "4":
                self.player_manager.manually_send_answers(self.score_obj, -1)



        except Exception as e:
            print(e)
            self.infolbl["text"] = f"Encountered a problem executing that key <{event.char}>"

    def enterEvent(self, event):
        self.infolbl["text"] = "Running..."
        self.clear_all_text()
        self.mainlbl["bg"] = self.defaultbg

        def enterThread():
            try:
                if not self.DEBUG:
                    self.infolbl["text"] = "Grabbing screenshot via ADB..."
                    self.adb_screencap(self.filename)
                    self.infolbl["text"] = "Processing image..."
                    question, answers = ScreenProcessor.process_file(self.filename)
                else:
                    self.infolbl["text"] = "Debug mode"
                    question, answers = self.DEBUG_LIST[0], self.DEBUG_LIST[1]
                # make question one line
                question = question.replace("\n", " ")
                # fix dates
                p = re.compile(r"([0-9]{4})5")
                question = (re.sub(p, "\g<1>s", question))
                # print(question)
                # for a in answers:
                #     print(a)
                self.mainlbl["text"] = question
                self.mainlbl["bg"] = "orange"
                if len(answers) == 3:
                    self.answer1lbl["text"] = answers[0] + ": "
                    self.answer2lbl["text"] = answers[1] + ": "
                    self.answer3lbl["text"] = answers[2] + ": "
                # time.sleep(1)
                self.infolbl["text"] = "Searching..."
                self.search(question, answers, self.question_num)
                self.infolbl["text"] = "Ready."
                self.question_num += 1
            except SyntaxError as e:
                print(e.msg)
                time.sleep(0.25)
            except Exception as e:
                self.infolbl["text"] = "Error proccessing screenshot. Message: " + str(e)

        threading.Thread(target=enterThread).start()

    class WrappingLabel(Label):
        '''a type of Label that automatically adjusts the wrap to the size'''

        def __init__(self, master=None, **kwargs):
            Label.__init__(self, master, **kwargs)
            self.bind('<Configure>', lambda e: self.config(wraplength=self.winfo_width()))

    def clear_all_text(self):
        newText = ""
        self.answer1whichlbl["text"] = newText
        self.answer2whichlbl["text"] = newText
        self.answer3whichlbl["text"] = newText
        self.answer1lbl["text"] = newText
        self.answer2lbl["text"] = newText
        self.answer3lbl["text"] = newText
        self.answer1scorelbl["text"] = newText
        self.answer2scorelbl["text"] = newText
        self.answer3scorelbl["text"] = newText
        self.keySentenceslbl["text"] = "Key Sentences here"
        self.googleSentenceslbl["text"] = "Google Snippets here"
        self.mainlbl["text"] = newText
        self.module1lbl["text"] = "0"
        self.module1Active = False
        self.table_built = False
        for i in self.tree.get_children():
            self.tree.delete(i)

    def run(self):
        window = Tk()
        window.title("QLive bot")
        window.geometry('700x500')
        # window.attributes('-fullscreen', True)
        window.state('zoomed')
        frame1 = Frame(relief=SOLID, bd=2)
        frame2 = Frame(relief=RAISED)
        frame3 = Frame()
        answerframe = Frame(frame3)
        # frame1.pack(fill=X)
        frame3.grid(column=0, row=0, sticky=(N, S, E, W))
        frame1.grid(column=1, row=0, sticky=(N, S, E, W))
        frame2.grid(column=0, row=1, sticky=(N, S, E, W), columnspan=2)
        window.grid_columnconfigure(0, weight=2, uniform="foo")
        window.grid_columnconfigure(1, weight=1, uniform="foo")
        window.grid_rowconfigure(0, weight=50)
        window.grid_rowconfigure(1, weight=1)
        self.imglbl = Canvas(frame1)
        self.imglbl.grid(column=0, row=0, sticky=(N, S, E, W))
        self.imgtextlbl = Label(frame1, text=" ", anchor=NW, justify=LEFT, wraplength=600)
        self.imgtextlbl.grid(column=0, row=1, sticky=(N, S, E, W))
        frame1.grid_rowconfigure(0, weight=5)
        frame1.grid_rowconfigure(1, weight=1)
        frame1.grid_columnconfigure(0, weight=1)

        answerfont = ("Helvetica", 12)
        scorefont = ("Helvetica", 16)

        self.mainlbl = Label(frame3, justify=LEFT, anchor=W,
                             text="Welcome to QLive bot. <Enter> to scan for question, <i> to run vision api. <s> to show previous image.")
        self.mainlbl.pack(fill=X)
        answerframe.pack(fill=X)
        self.answer1lbl = Label(answerframe, justify=LEFT, text="answer 1:", font=answerfont)
        self.answer2lbl = Label(answerframe, justify=LEFT, text="answer 2:", font=answerfont)
        self.answer3lbl = Label(answerframe, justify=LEFT, text="answer 3:", font=answerfont)
        self.answer1lbl.grid(column=0, row=1, sticky="w")
        self.answer2lbl.grid(column=0, row=2, sticky="w")
        self.answer3lbl.grid(column=0, row=3, sticky="w")

        self.answer1scorelbl = Label(answerframe, justify=LEFT, text="10 (99)", width=10, font=scorefont)
        self.answer2scorelbl = Label(answerframe, justify=LEFT, text="10 (99)", width=10, font=scorefont)
        self.answer3scorelbl = Label(answerframe, justify=LEFT, text="10 (99)", width=10, font=scorefont)
        self.answer1scorelbl.grid(column=1, row=1, sticky="w")
        self.answer2scorelbl.grid(column=1, row=2, sticky="w")
        self.answer3scorelbl.grid(column=1, row=3, sticky="w")

        self.answer1whichlbl = Label(answerframe, justify=LEFT, text="| Interesting title 1")
        self.answer2whichlbl = Label(answerframe, justify=LEFT, text="| Interesting title 2")
        self.answer3whichlbl = Label(answerframe, justify=LEFT, text="| Interesting title 3")
        self.answer1whichlbl.grid(column=2, row=1, sticky="w")
        self.answer2whichlbl.grid(column=2, row=2, sticky="w")
        self.answer3whichlbl.grid(column=2, row=3, sticky="w")

        framepadx = 5
        framepady = 5

        googlesnippetframe = Frame(frame3, relief=SOLID, bd=2)
        googlesnippetframe.pack(fill=X, padx=framepadx, pady=(10, 0))
        self.googleSentenceslbl = self.WrappingLabel(googlesnippetframe, anchor=NW, justify=LEFT,
                                                     text="Google snippet box" * 20)
        self.googleSentenceslbl.pack(fill=X)

        keysentencesframe = Frame(frame3, relief=SOLID, bd=2, height=250)
        keysentencesframe.pack(fill=X, padx=framepadx, pady=framepady, expand=False)
        keysentencesframe.pack_propagate(0)  # allows fixed height
        self.keySentenceslbl = self.WrappingLabel(keysentencesframe, justify=LEFT, anchor=NW,
                                                  text="Key sentences here" * 10)
        self.keySentenceslbl.pack(fill=X)

        tableframe = Frame(frame3, relief=SOLID, bd=2, height=250)
        tableframe.pack(fill=X, padx=framepadx, pady=framepady, expand=False)
        tableframe.pack_propagate(0)  # allows fixed height
        self.tree = ttk.Treeview(tableframe, columns=["Table to go here"], show="headings")
        self.tree.grid(column=0, row=0, sticky='nsew')
        vsb = ttk.Scrollbar(tableframe, orient="vertical", command=self.tree.yview)
        hsb = ttk.Scrollbar(tableframe, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        hsb.grid(column=0, row=1, sticky='ew')
        vsb.grid(column=1, row=0, sticky='ns')
        tableframe.grid_columnconfigure(0, weight=1)
        tableframe.grid_rowconfigure(0, weight=1)

        module_frame = Frame(frame3)
        module_frame.pack(fill=X, padx=framepadx, pady=framepady)
        self.module1lbl = Label(module_frame, justify=LEFT, anchor=NW)
        self.module1lbl.pack(fill=X)
        self.module1Active = False
        self.module1Results = [" ", " ", " "]
        self.infolbl = Label(frame2, text=" ", justify=LEFT, anchor=SW)
        self.infolbl.pack(side=LEFT, fill=BOTH)
        window.bind("<Key>", self.keyEvent)
        window.bind("<Return>", self.enterEvent)
        if not self.DEBUG:
            threading.Thread(target=self.setupThread).start()
        # start livefeed thread
        t = threading.Thread(target=self.live_feed_thread)
        t.start()

        t1 = threading.Thread(target=self.queue_thread)
        t1.start()

        self.clear_all_text()
        window.update()  # needed to prevent problems with width/height measurements later
        self.defaultbg = window.cget('bg')
        window.mainloop()

    def adb_screencap(self, filename):
        start_time = time.time()
        cmd = "adb exec-out screencap -p > %s" % filename
        # print(cmd)
        if subprocess.call(cmd, shell=True) != 0:
            raise NameError("Couldn't initiate ADB. Retrying...")
        elapsed_time = time.time() - start_time
        print(elapsed_time)

    def setupThread(self):
        self.infolbl["text"] = "Starting ADB..."
        while True:
            try:
                self.adb_screencap(self.filename)
                break
            except NameError as e:
                # self.infolbl["text"] = str(e)
                time.sleep(0.5)

        self.infolbl["text"] = "Successfully initiated ADB. Ready."

    def run_without_screenshot_blocking(self, question, answers, data_obj):
        self.infolbl["text"] = "Running..."
        self.clear_all_text()
        self.mainlbl["bg"] = self.defaultbg
        try:
            self.infolbl["text"] = "Blind mode..."
            # make question one line
            question = question.replace("\n", " ")
            self.mainlbl["text"] = question
            self.mainlbl["bg"] = "orange"
            if len(answers) == 3:
                self.answer1lbl["text"] = answers[0] + ": "
                self.answer2lbl["text"] = answers[1] + ": "
                self.answer3lbl["text"] = answers[2] + ": "
            # time.sleep(1)
            self.infolbl["text"] = "Searching..."
            self.search(question, answers, self.question_num, data_obj=data_obj)
            self.infolbl["text"] = "Ready."
            self.question_num += 1
        except SyntaxError as e:
            print(e.msg)
            time.sleep(0.25)
        except Exception as e:
            self.infolbl["text"] = "Error run_without_screenshot. Message: " + str(e)

    def live_feed_thread(self):
        livefeed_obj = LiveFeed.LiveFeed()
        self.infolbl["text"] = "Starting LiveFeed thread"
        # ids, times, types = livefeed_obj.get_next_game() #migrate return value to dictionary
        d = livefeed_obj.get_next_game()
        ids = d.get("ids")
        times = d.get("times")
        types = d.get("types")
        hosts = d.get("hosts")
        if hosts:
            if len(hosts) >= 1:
                host = hosts[0]
                print(f"gui: live_feed_thread: host: {host}")
            else:
                host = "api-prod--002.uk.theq.live"
        else:
            host = "api-prod--002.uk.theq.live"
            print("gui: live_feed_thread: host: None. TODO handle this.\n-- RESTART PROGRAM!! --")
            # TODO Handle this, will need to restart getting next game

        # host = "api-prod--002.uk.theq.live"
        # create virtual players here
        self.player_manager = PlayerManager.PlayerManager(100, ids[0])

        print(f"Types: {types}")
        start = datetime.time(18, 50, 0)
        end = datetime.time(19, 10, 0)
        time_now = datetime.datetime.now().time()
        if time_in_range(start, end, time_now):
            print("Time is spelling q")
            self.gameType = "The Spelling Q"
        else:
            self.gameType = types[0]
        print(f"gui: Gametype: {self.gameType}")
        # self.queue.put({"question":"hey?", "answers":["Hello", "Hellosajdk", "hopsad"]}) #to test spellcheck
        while True:
            if times[0] / 1000 < (time.time() + 3600):
                livefeed_obj.get_stream(ids[0], queue=self.queue, host=host)
                print(f"LiveFeed died, restarting... ID: {ids[0]}")
            else:
                print(f"Game starts in {round(times[0]/1000-time.time())+3600}s")
            time.sleep(1)

    def queue_thread(self):
        # polls queue.Queue object for questions and answers from live feed thread and executes in blocking way to avoid simultaneous exeuction
        while True:
            try:
                dic = self.queue.get()
                if dic.get("question"):
                    # this is if a gamestart event has occured
                    question = dic.get("question")
                    answers = dic.get("answers")
                    data_obj = dic.get("data_obj")
                    if " Spelling " in self.gameType:
                        print("gui: Running spell checker")
                        self.run_spellchecker(question=question, answers=answers, data_obj=data_obj)
                    else:
                        self.run_without_screenshot_blocking(question, answers, data_obj)
                else:
                    # gameresult event {"question_ID":question_ID, "choice_ID":choice_ID, "choice_human_string":choice_human_string}
                    question_ID = dic.get("question_ID")
                    choice_ID = dic.get("choice_ID")
                    choice_human_string = dic.get("choice_human_string")
                    if question_ID and choice_ID and choice_human_string:
                        self.player_manager.append_correct_response(question_ID, choice_ID, choice_human_string)
                    else:
                        print(f"gui: queue_thread couldn't get all vars for correct response")
            except Exception as e:
                print(f"queue_thread: Exception {e}")


if __name__ == "__main__":
    m = Main()
    m.run()
