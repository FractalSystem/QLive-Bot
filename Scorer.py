from bs4 import BeautifulSoup
from bs4.element import Comment
from math import exp
from MyUtilities import sanitise_text
import ProximityScorePlugin
import json
import threading
import re
import time

DEBUG = False
EXP_FACTOR = -0.3  # smaller means less fall off with repeated words in the same article
WIKI_MULTIPLIER = 1  # multiplier for wikipedia.org domain
TITLE_SCORE = 3  # bonus points for answer being present in title
DESC_SCORE = 2  # bonus points for answer being present in description
PROX_SCORE_MULTIPLIER = 1  # bonus points for words in answer being close to words in answer
ENABLE_LOG = True


class Scorer:
    """ Class respoonsible for scoring answers based on Google results and crawled webpages. """

    def __init__(self, question, answers, not_question, question_num, mainlbl):
        self.question = question
        self.answers = answers
        self.not_question = not_question
        self.question_num = question_num
        self.sanitised_question = sanitise_text(question)
        self.sanitised_answers = [sanitise_text(clean_answer) for clean_answer in answers]
        self.scores = []
        self.google_scores = []
        self.snippet = ""
        self.mainlbl = mainlbl
        self.which_results = ["", "", ""]
        self.data_obj = None
        self.table = None  # put as dictionary: {"headers":, "rows":}
        for a in range(len(answers)):
            self.scores.append(0)
            self.google_scores.append(0)
        self.sanitised_question_split = ProximityScorePlugin.split_question(question)
        self.key_sentences = {}
        self.sentences = {}
        for a in self.sanitised_answers:
            self.key_sentences[a] = []
            self.sentences[a] = []
        if ENABLE_LOG:
            t = threading.Thread(target=self.log_question)
            t.start()

    def log_question(self):
        try:
            with open("question_log.log", "a") as f:
                f.write(json.dumps((self.sanitised_question, self.sanitised_answers)) + "\n")
        except Exception:
            pass

    def set_data_obj(self, data_obj):
        self.data_obj = data_obj

    def set_snippet(self, snippet):
        # sets the snippet from google scraper
        self.snippet = snippet

    def get_snippet(self):
        return self.snippet

    def get_question_num(self):
        return self.question_num

    def get_question(self):
        return self.question

    def get_answers(self):
        return self.answers

    def get_scores(self):
        # if self.not_question:
        #     s = []
        #     score_sum = sum(self.scores)
        #     for score in self.scores:
        #         s.append(score_sum-score)
        #     return s
        # else:
        #     return self.scores
        return self.scores

    def get_key_sentences(self):
        return self.key_sentences

    def get_not_question(self):
        return self.not_question

    def get_google_scores(self):
        return self.google_scores

    def set_text_mainlbl(self, text):
        self.mainlbl["text"] = text

    def set_which_results(self, which_results):
        self.which_results = which_results

    def get_which_results(self):
        return self.which_results

    def get_table(self):
        return self.table

    def set_table(self, table):
        self.table = table

    def get_best_answers(self):
        # returns list of index of best score, or possible candidates
        high_score = 0
        # handle not question logic by flipping scores
        if self.not_question:
            print("Scorer: Handling 'not' question")
            s = []
            score_sum = sum(self.scores)
            for score in self.scores:
                s.append(score_sum - score)
            scores = s
        else:
            scores = self.scores

        # define minimum threshold at which to randomise scores
        if sum(self.scores) <= 2:
            return list(range(0, len(self.scores)))  # returns [0,1,2]

        google_scores = self.google_scores

        # check if google scores are conclusive:
        if google_scores.count(0) == len(google_scores) - 1 and not self.not_question:
            return [google_scores.index(max(google_scores))]

        max_value = max(scores)
        max_index = scores.index(max_value)
        # check if max value of list is 1.4x greater than the other ones
        good = True
        candidates = [max_index]
        for i, score in enumerate(scores):
            if i != max_index:
                if score * 1.3 >= max_value:
                    good = False
                    candidates.append(i)

        if good:
            return [max_index]
        else:
            # we have some close values. Return a list of candidates
            return candidates

    def score_web_content(self, type, content, url):
        """
        Called by AsyncSearcher when url is loaded
        TYPES: 0: forward search 1: backwards search 2: google suggestion box
        """
        multiplier = 1
        if "wikipedia.org" in url:
            multiplier = WIKI_MULTIPLIER
        if type == 0:
            if DEBUG:
                print(f"Scoring {url}")
            t = time.time()
            self.score_forwards(content, multiplier)
            # print(f"Scorer: score_forwards took {time.time()-t}s")
            t = time.time()
            self.fetch_sentences(content)
            # print(f"Scorer: fetch_sentences took {time.time()-t}s")
            # self.score_sentences(content, multiplier)  # turns out to be rather useless

    def tag_visible(self, element):
        if element.parent.name in ['style', 'script', 'head', 'title', 'meta', '[document]']:
            return False
        if isinstance(element, Comment):
            return False
        return True

    def text_from_html(self, body):
        soup = BeautifulSoup(body, 'lxml')
        texts = soup.findAll(text=True)
        visible_texts = filter(self.tag_visible, texts)
        return u" ".join(t.lower().strip() for t in visible_texts)

    def score_forwards(self, content, multiplier):
        """Scores content based purely on occurences"""
        # text = BeautifulSoup(content, features="html.parser").get_text().lower() depreciated 19/03/19
        t = time.time()
        text = self.text_from_html(content)
        # print(f"Scorer: cleaning took {time.time()-t}")
        clean_text = sanitise_text(text)
        for i, answer in enumerate(self.sanitised_answers):
            s = f"\\b{answer}\\b"
            p = re.compile(s)
            occurrences = len(re.findall(p, clean_text))
            score = 0
            for n in range(occurrences):
                score += exp(n * EXP_FACTOR)
            self.scores[i] += score * multiplier
            if DEBUG:
                print(
                    f"Incremented score for answer {str(i)} by {str(score*multiplier)} based on {occurrences} occurrences")

    def score_titles(self, titles):
        """Scores google titles"""
        # for title in titles:
        #     for i in range(len(self.sanitised_answers)):
        #         if self.sanitised_answers[i] in sanitise_text(title):
        #             self.google_scores[i] += TITLE_SCORE
        #             self.scores[i]+=TITLE_SCORE

        for i, answer in enumerate(self.sanitised_answers):
            s = f"\\b{answer}\\b"
            p = re.compile(s)
            titles_string = " ".join(titles)
            l = len(re.findall(p, sanitise_text(titles_string)))
            self.google_scores[i] += l * TITLE_SCORE
            self.scores[i] += l * TITLE_SCORE

    def score_descriptions(self, descs):
        """Scores google descriptions"""
        # for desc in descs:
        #     # print(desc)
        #     for i in range(len(self.sanitised_answers)):
        #         if self.sanitised_answers[i] in desc.lower():
        #             self.google_scores[i] += DESC_SCORE
        #             self.scores[i] += DESC_SCORE

        for i, answer in enumerate(self.sanitised_answers):
            s = f"\\b{answer}\\b"
            p = re.compile(s)
            descs_string = " ".join(descs)
            l = len(re.findall(p, sanitise_text(descs_string)))
            self.google_scores[i] += l * DESC_SCORE
            self.scores[i] += l * DESC_SCORE

    def score_sentences(self, content, multiplier):  # currently depreciated and unused
        """Score increments are points to update each answer with, match list contains a list of [match, sentence] pairs"""
        score_increments, match_list = ProximityScorePlugin.run(self.sanitised_question_split, self.sanitised_answers,
                                                                content)
        print(score_increments)
        print(match_list)
        for i in range(len(score_increments)):
            self.scores[i] += score_increments[i] * PROX_SCORE_MULTIPLIER * multiplier

    def fetch_key_sentences(self, content):
        """internally used by method fetch_sentences"""
        score_increments, key_sentences = ProximityScorePlugin.run(self.sanitised_question_split,
                                                                   self.sanitised_answers,
                                                                   content)
        for key in key_sentences:
            self.key_sentences[key].append(key_sentences[key])

    def fetch_sentences(self, content):
        """Gets sentences with q and a in and filters to get key ones"""
        score_increments, sentences = ProximityScorePlugin.run(self.sanitised_question_split,
                                                               self.sanitised_answers,
                                                               content)
        for key in sentences:
            self.sentences[key].append(sentences[key])
        # print(self.sentences)
        # get key sentences of this round
        key_sentences = ProximityScorePlugin.get_key_sentences(self.sentences, self.sanitised_question_split)
        # append them to self.key_sentences
        for key in key_sentences:
            if key_sentences[key] not in self.key_sentences[key]:
                self.key_sentences[key].append(key_sentences[key])
        self.finalise_key_sentences()  # added to reduce to one sentence per answer
        # print(f"Best Sentences: {self.key_sentences}")

    def finalise_key_sentences(self):
        """Final method called to reduce key sentences to 1 per answer"""
        # remove long sentences
        for key in self.key_sentences:
            self.key_sentences[key] = [x for x in self.key_sentences[key] if len(x) < 200]
        # get the best
        key_sentences = ProximityScorePlugin.get_key_sentences(self.key_sentences, self.sanitised_question_split)
        for key in key_sentences:
            self.key_sentences[key] = [key_sentences[key]]


if __name__ == "__main__":
    s = Scorer.get_best_answers(None)
    print(s)
