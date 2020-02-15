from bs4 import BeautifulSoup
import re
from MyUtilities import sanitise_text, sanitise_text_no_lower
from nltk import pos_tag, sent_tokenize
import time

DEBUG = False

""" Experimental extension to produce better scores based on some rudimentary NL processing. 
Split answer into words, search for each of the words in the sentence, if it's in same sentance as a noun from the question
then ascribe bonus points to that answer."""


def split_answers(answers):
    """splits word in answers and removes words like 'the' which would be dumb to match"""
    l = []
    reject_re = re.compile(r"(the)")
    for answer in answers:
        l.append([x for x in answer.split(" ") if len(re.findall(reject_re, x)) == 0])
    return l


def construct_patterns(answers, split_ques):
    """ builds pattern from question words and words in answers. Note that it doesnt match trailing word boundary to allow for plurals"""
    # print(split_ques)
    q_s = ""
    patterns = []
    for word in split_ques:
        q_s += word
        q_s += "|"
    for ans in answers:
        a_s = ""
        # for word in ans:
        #     a_s += word
        #     a_s += "|"
        forward_pattern = "\\b({}).*?\\b(?:{})".format(ans, q_s[:-1])
        reversed_pattern = "\\b(?:{}).*?\\b({})".format(q_s[:-1], ans)
        patterns.extend([re.compile(forward_pattern), re.compile(reversed_pattern)])
        # print(forward_pattern, reversed_pattern)
    return patterns


def OLDget_answer_index(answers_split, word):
    """ Gets index based on the regex pattern match (assumes answer is padded with space at start)"""
    for i in range(len(answers_split)):
        for ans_word in answers_split[i]:
            if ans_word == word:
                return i


def get_answer_index(answers, answer):
    """ Gets index based on the regex pattern match (assumes answer is padded with space at start)"""
    for i in range(len(answers)):
        if answers[i] == answer:
            return i


def split_question(question):
    """question will be passed in pre split to improve performance"""
    # start_time = time.time()
    try:
        a = pos_tag(sanitise_text_no_lower(question).split(" "))
    except IndexError as e:
        print(
            "Pos tagger messed up for some reason,\n this was thought to have been fixed by removing double and triple spaces\nAre there higher multiple spaces in the question? {e}")
        return sanitise_text_no_lower(question).split(" ")
    if DEBUG:
        print(a)

    sanitised_question_split = [sanitise_text(x[0]) for x in a if "NN" in x[1] or "JJ" in x[1] or "RB" in x[1]]
    # print("--- %s seconds ---" % (time.time() - start_time))
    if DEBUG:
        print(sanitised_question_split)
    return sanitised_question_split


def run(sanitised_question_split, sanitised_answers, content):
    """Return key sentences in dict of style {answer: [sentences]}"""
    score_increments = [0, 0, 0]
    # answers_split = split_answers(sanitised_answers)
    soup = BeautifulSoup(content, features='html.parser')
    data = soup.findAll(text=True)

    def visible(element):
        if element.parent.name in ['style', 'script', '[document]', 'head', 'title']:
            return False
        elif re.match('<!--.*-->', str(element.encode('utf-8'))):
            return False
        return True

    result = filter(visible, data)
    m = []
    for s in list(result):
        if "\n" not in s:
            r = sent_tokenize(s)
            if len(r) > 0:
                m.extend(r)
    # print(m)
    patterns = construct_patterns(sanitised_answers, sanitised_question_split)
    good_matches = []  # first element is sentence, second is the matched answer
    for sentence in m:
        for pattern in patterns:
            match = re.findall(pattern, sanitise_text(sentence))
            if len(match) > 0:
                good_matches.append([match[0], sentence])
    sentences = {}
    for match in good_matches:
        sentences[match[0]] = match[1]
        answer = match[0]
        index = get_answer_index(sanitised_answers, answer)
        score_increments[index] += 1

    # key_sentences = get_key_sentences(good_matches, sanitised_question_split)
    return score_increments, sentences


def get_best_sentence(sentence_list, split_question):
    high_score = 0
    winning_sentences = []
    for s in sentence_list:
        sentence = sanitise_text(s)
        score = 0
        for word in split_question:
            if sentence.find(word) != -1:
                score += 1
        if score > high_score:
            high_score = score
            winning_sentences = [s]
        elif score == high_score:
            winning_sentences.append(s)

    def get_shortest_sentence(sentences):
        shortest_length = 10000000
        winning_sentence = None
        for e in winning_sentences:
            if len(e) < shortest_length and len(e.split(" ")) > 5:  # shortest but more than 5 words please
                winning_sentence = e
        return winning_sentence

    winning_sentence = get_shortest_sentence(winning_sentences)
    if DEBUG:
        print(f"Best Sentence = {winning_sentence}, Score = {high_score}")
    return winning_sentence


def get_key_sentences(good_matches, split_q):
    """check if matches are conflicting and remove duplicates, if not return the sentence with the most keyword matches, then the shortest, if so then return the
    most relevent, then the shortest sentence for each match
    good_matches is dict of form {answer: [sentences], ...}
    """
    seen_dict = {}
    for key in good_matches:
        answer = key
        sentences = good_matches[key]
        if answer not in seen_dict:
            seen_dict[answer] = sentences
        else:
            seen_dict[answer].extend(sentences)
    # print(f"seen_dict: {seen_dict}")
    good_dict = {}
    for key in seen_dict:
        # good_dict[key] = get_best_sentence(seen_dict[key], split_q)
        best_sentence = get_best_sentence(seen_dict[key], split_q)
        if best_sentence is not None:
            good_dict[key] = best_sentence
    # print(good_dict)
    return good_dict


def in_context_run():
    # Debug function
    start_time = time.time()
    with open("test.txt", "rb") as f:
        content = f.read()
    answers = [sanitise_text("mnangagwa"), sanitise_text("Mugabe"), sanitise_text("May")]
    question_raw = "president of Zimbabwe?"
    split_q = split_question(question_raw)
    score_increments, key_sentences = run(split_q, answers, content)
    print(score_increments)
    print(key_sentences)
    print("--- %s seconds ---" % (time.time() - start_time))


if __name__ == "__main__":
    in_context_run()
