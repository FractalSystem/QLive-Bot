import requests
import re
import urllib3
import urllib.parse
from bs4 import BeautifulSoup
import time
from requests_threads import AsyncSession

# r = "<h3 class=\"r\"><a.*?>(.*?)</a></h3>"
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

NUM_OF_RESULTS = 15


class GoogleScrape():
    """ Class performs google searches and returns results. """

    def __init__(self):
        self.googleSearch = "https://www.google.co.uk/search?q=%s&num=%s"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/67.0.3396.99 Safari/537.36"}
        # self.search()

    def search(self, query, number_of_results=NUM_OF_RESULTS):
        start_time = time.time()
        # print(self.googleSearch % (query, number_of_results))
        f = {'query': query, "num": number_of_results}
        url = "https://www.google.co.uk/search?" + urllib.parse.urlencode(f)
        # print(url)
        r = requests.get(url, verify=False, headers=self.headers)
        # pattern to match title
        title_pattern = re.compile(r"<h3 class=\".*?\">(.*?)</h3>")
        # old title_pattern = re.compile(r"<h3 class=\"r\"><a.*?>(.*?)</a></h3>")
        # pattern to match url
        url_pattern = re.compile(r"<div class=\"r\"><a href=\"(.*?)\".*?</div>")
        # old url_pattern = re.compile(r"<h3 class=\"r\"><a href=\"(.*?)\".*?</h3>")
        # pattern to match desc
        desc_pattern = re.compile(r"<span class=\"st\">(.*?)</span>")
        desc_correction_pattern = re.compile(r"<span class=\"f\">.*?</span>")
        # with open("results.txt", "wb") as f:
        #     f.write(str.encode(r.content.decode()))
        content = r.content.decode()
        snippet_pattern = re.compile(r"<div class=\"LGOjhe\".*?</div>")
        match_snippet = re.findall(snippet_pattern, content)
        dob_pattern = re.compile(r"<div class=\"Z0LcW\">(.*?)</div>")
        dob_snippet = re.findall(dob_pattern, content)
        word_pattern = re.compile(r"<span data-dobid=\"hdw\">(.*?)</span>")
        match_spelling = re.findall(word_pattern, content)
        if len(match_spelling) > 0:
            match_spelling = match_spelling[0]
        else:
            match_spelling = "No match found"

        if len(dob_snippet) > 0:
            dob = dob_snippet[0]
        else:
            dob = "No Date Found"
        google_snippet = ""
        for snippet in match_snippet:
            soup = BeautifulSoup(snippet, 'html.parser')
            texts = soup.findAll(text=True)
            google_snippet = "".join(t for t in texts)

        # print(r.content.decode().find("th the birth"))

        match_url = re.findall(url_pattern, content)
        match_desc = re.findall(desc_pattern, re.sub(desc_correction_pattern, "", content))
        match_title = re.findall(title_pattern, content)

        for url in match_url:
            # print(url)
            pass
        for desc in match_desc:
            # print(desc)
            pass
        for title in match_title:
            # print(title)
            pass
        elapsed_time = time.time() - start_time
        print(f"GoogleScrape: Retrieved google results in {round(elapsed_time, 3)}s")
        return [match_url, match_title, match_desc, google_snippet, dob, match_spelling]
