import asyncio
import aiohttp
import time
import async_timeout
import threading
from GoogleScrape import GoogleScrape
from MyUtilities import sanitise_text
from multiprocessing.dummy import Pool as ThreadPool
import re
from html import unescape
import unicodedata

FETCH_TIMEOUT = 2
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36"}
DEEP_SEARCH_FIRST_NUM = 10  # number of urls to deep search (ie load page and search inside page), 0 means all


class AsyncSearcher:
    def __init__(self, google_results, score_obj):
        if DEEP_SEARCH_FIRST_NUM != 0:
            self.urls = google_results[0][:DEEP_SEARCH_FIRST_NUM]
        else:
            self.urls = google_results[0]
        # print(self.urls)
        self.titles = google_results[1]
        self.descriptions = google_results[2]
        self.score_obj = score_obj
        self.answers = self.score_obj.get_answers()
        self.not_question = score_obj.get_not_question()
        self.print_active = True
        self.which_results = ["", "", ""]

        self.contents = []

        self.run()

    async def get_urls(self):
        # fetches urls and scores by calling score_obj.score_web_content
        async with aiohttp.ClientSession(headers=HEADERS, loop=asyncio.get_running_loop(),
                                         connector=aiohttp.TCPConnector(verify_ssl=False)) as session:
            time_start = time.time()
            print(self.urls)
            tasks = [self.get_url(session, url, i) for i, url in enumerate(self.urls)]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for content in self.contents:
                self.score_obj.score_web_content(0, content, "")

            # print("Scored web content")

            # can set best table here
            self.print_active = False
            # print(results)
            self.score_obj.finalise_key_sentences()

    async def get_url(self, session, url, index_on_google):
        with async_timeout.timeout(FETCH_TIMEOUT):
            async with session.get(url) as response:
                print(f"Fetching url {index_on_google}")
                content = await response.text()
                # threading.Thread(target = lambda : self.score_obj.score_web_content(0, content, url)).start() #seems to fix performance a bit, kind of dirty though
                # self.score_obj.score_web_content(0, content, url) # this is a heavy performance hit. Migrate to call after async search finishes
                self.contents.append(content)
                # if no table has been found yet then test this page for a table, would like to score then set the table based on whats best
                if index_on_google == 0:
                    print("Got first result")
                    if not self.score_obj.get_table():
                        self.handle_table(content)
                return response.status

    def compare_string(self, string, answer):
        # method which fuzzily checks for answer in row and returns a score = num_matches/num_words_in_answer
        clean_string = string.lower().strip()
        # if len(clean_string) > 200:
        #     return 0
        words = answer.lower().split(" ")
        num_words = len(words)
        matched_words = 0
        for word in words:
            if clean_string.find(word) != -1:
                # print(f"Word: {word}, clean_string: {clean_string}")
                matched_words += 1
        score = matched_words / num_words
        # print(f"String: {string}, scored: {score}")
        return score

    def search_table(self, clean_rows):  # searches pythonic table for answers in a single column,
        # returns "possible_columns", a list of scores of each column and good_rows, a list of indexes of
        # rows containing the answers
        # initiate list to length of longest row
        l = 0
        for col in clean_rows:
            # print(col)
            if len(col) > l:
                l = len(col)
        possible_columns = [0] * l
        good_rows = []
        # we now have list of rows, each row is a list of columns.
        for i, row in enumerate(clean_rows):
            for l, col in enumerate(row):
                # search for answers in columm and append to list of good columns with score, assume all answers are in same column
                for answer in self.answers:
                    score = self.compare_string(col, answer)
                    if score > 0.5:
                        possible_columns[l] += score
                        good_rows.append(i)
        # print(possible_columns)
        return possible_columns, good_rows

    def process_table(self, table):
        # breaks raw <table> into pythonic list of rows, each a list of columns
        row_pattern = re.compile(r"<tr.*?>.*?</tr>")
        data_pattern = re.compile(r"<td.*?>.*?</td>")
        tag_pattern = re.compile(r"<.*?>")
        heading_pattern = re.compile(r"<th.*?>.*?</th>")
        rows = re.findall(row_pattern, table)
        clean_rows = []
        headers = []
        if rows is not None:
            clean_cols = []
            for row in rows:
                h = re.findall(heading_pattern, row)
                if h:
                    for header in h:
                        clean_cols.append(
                            unicodedata.normalize("NFKD", unescape(re.sub(tag_pattern, "", header).strip())))
                    break
                else:
                    clean_cols.append(["-"])  # experimental
            # print(f"Headers: {clean_cols}")
            headers.append(clean_cols)
            # clean_rows.append(clean_cols)
            for row in rows:
                clean_cols = []
                cols = re.findall(data_pattern, row)
                for col in cols:
                    clean_cols.append(unicodedata.normalize("NFKD", unescape(re.sub(tag_pattern, "", col).strip())))
                clean_rows.append(clean_cols)
            # print(f"Clean_rows: {clean_rows}")
            return clean_rows, headers

    def handle_table(self, html):
        # store table in dictionary for a particular page
        # for each table call score object search_table to get possible rows and columns
        # handle each case of number of rows

        html = html.replace("\n", " ")
        table_pattern = re.compile(r"<table.*?>.*?</table>")
        tables = re.findall(table_pattern, html)
        if tables is not None:
            rows = []
            for table in tables:
                # print(table)
                clean_rows, headers = self.process_table(table)
                possible_columns, good_rows = self.search_table(clean_rows)
                if len(possible_columns) > 1:
                    # the answers are in different columns, this is likely problematic.
                    pass
                if len(good_rows) >= len(self.answers):
                    self.set_table(headers, [clean_rows[i] for i in good_rows])
                    return
                if len(good_rows) < len(self.answers):
                    # the answer may be in multiple tables?
                    rows.extend([clean_rows[i] for i in good_rows])
            if len(rows) > len(self.answers):
                max_w = 0
                for row in rows:
                    l = len(row)
                    if l > max_w:
                        max_w = l
                l = ["multi-row Table"]
                l2 = [str(i) for i in range(max_w - 1)]
                l.extend(l2)
                print(l)
                self.set_table([l], rows)

    def set_table(self, headers, rows):
        d = {"headers": headers, "rows": rows}
        self.score_obj.set_table(d)

    def which_question_search(self):
        # search question + answer and score based on occurence of question in titles and descs. Doesn't work rn
        question = " ".join(self.score_obj.sanitised_question_split)

        # internal def for threading purposes
        def internal_search(in_list):
            # in_list[0] is question, in_list[1] is answer
            # num results = 2 to avoid weird little inconsistencies in google search
            google_results = GoogleScrape().search(sanitise_text(in_list[0] + " " + in_list[1]), number_of_results=2)
            if len(google_results[1]) > 0:
                try:
                    return google_results[1][0], google_results[2][0]
                except Exception as e:
                    print(f"AsyncSearcher: Exception {e}")
                    return "", ""
            else:
                print("AsyncSearcher: Which title search falied in Async")
                return "", ""

        in_list = []
        for answer in self.score_obj.get_answers():
            in_list.append([question, answer])
            # score google results
        pool = ThreadPool(3)
        results = pool.map(internal_search, in_list)  # results is tuple of titles and descs
        i = self.check_which_results(results)
        print(results)
        if i != -1:
            l = list(results[i])  # tuples are immutable so must convert to list first
            l[0] += "V. CONFIDENT"
            results[i] = tuple(l)
        self.which_results = [r[0] for r in results]
        self.score_obj.set_which_results(self.which_results)

    def check_which_results(self, results):
        titles = [r[0] for r in results]
        descs = [r[1] for r in results]
        answers = self.score_obj.get_answers()
        scores = [0, 0, 0]
        for desc in descs:
            for i, answer in enumerate(answers):
                if answer.lower() in desc.lower():
                    scores[i] += 1
        # if this fails do a fuzzy search
        if scores == [0, 0, 0]:
            for desc in descs:
                # print(desc)
                for i, answer in enumerate(answers):
                    score = self.compare_string(desc, answer)
                    scores[i] += score
        # this loop checks if only one answer has a score>=1. If it does then return that answer's index, if not return -1
        f = -1
        for i, score in enumerate(scores):
            if score > 1:
                if f != -1:
                    return -1
                else:
                    f = i

        return f
        # check if which results has only one answer in two or more descs. Might be a bit dirty

    def run(self):
        start_time = time.time()
        t = threading.Thread(target=self.which_question_search)
        t.start()
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(self.get_urls())
        loop.close()
        t.join()
        elapsed_time = time.time() - start_time
        print(f"AsyncSearcher: total run time: {round(elapsed_time,3)}s")

