"""VQA accuracy, as the official VQA evaluation defines it.

This reimplements the scoring of the reference script (`vqaEval.py` in GT-Vision-Lab/VQA, BSD-licensed): a candidate
answer scores, for each of the ten human answers, ``min(1, matches among the other nine / 3)``, and the question's score
is the mean of those ten. Answers are normalised, on both sides, only when the humans disagree (the reference's own
rule), by removing punctuation, mapping number words to digits, dropping articles and expanding contractions. The
tables below are the reference's. Normalisation is exposed separately so results can be re-scored.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from typing import Any

CONTRACTIONS = {
    "'ow'sat": "'ow's'at",
    "'ows'at": "'ow's'at",
    "I'dve": "I'd've",
    "Id've": "I'd've",
    'Im': "I'm",
    'Ive': "I've",
    'aint': "ain't",
    'arent': "aren't",
    'cant': "can't",
    "couldn'tve": "couldn't've",
    'couldnt': "couldn't",
    "couldnt've": "couldn't've",
    'couldve': "could've",
    'didnt': "didn't",
    'doesnt': "doesn't",
    'dont': "don't",
    "hadn'tve": "hadn't've",
    'hadnt': "hadn't",
    "hadnt've": "hadn't've",
    'hasnt': "hasn't",
    'havent': "haven't",
    "he'dve": "he'd've",
    'hed': "he'd",
    "hed've": "he'd've",
    'hes': "he's",
    'howd': "how'd",
    'howll': "how'll",
    'hows': "how's",
    'isnt': "isn't",
    "it'dve": "it'd've",
    'itd': "it'd",
    "itd've": "it'd've",
    'itll': "it'll",
    "let's": "let's",
    'maam': "ma'am",
    "mightn'tve": "mightn't've",
    'mightnt': "mightn't",
    "mightnt've": "mightn't've",
    'mightve': "might've",
    'mustnt': "mustn't",
    'mustve': "must've",
    'neednt': "needn't",
    'notve': "not've",
    'oclock': "o'clock",
    'oughtnt': "oughtn't",
    "ow's'at": "'ow's'at",
    'shant': "shan't",
    "she'dve": "she'd've",
    "she's": "she's",
    "shed've": "she'd've",
    "shouldn'tve": "shouldn't've",
    'shouldnt': "shouldn't",
    "shouldnt've": "shouldn't've",
    'shouldve': "should've",
    "somebody'd": 'somebodyd',
    "somebody'dve": "somebody'd've",
    "somebodyd've": "somebody'd've",
    'somebodyll': "somebody'll",
    'somebodys': "somebody's",
    "someone'dve": "someone'd've",
    'someoned': "someone'd",
    "someoned've": "someone'd've",
    'someonell': "someone'll",
    'someones': "someone's",
    "something'dve": "something'd've",
    'somethingd': "something'd",
    "somethingd've": "something'd've",
    'somethingll': "something'll",
    'thats': "that's",
    "there'dve": "there'd've",
    'thered': "there'd",
    "thered've": "there'd've",
    'therere': "there're",
    'theres': "there's",
    "they'dve": "they'd've",
    'theyd': "they'd",
    "theyd've": "they'd've",
    'theyll': "they'll",
    'theyre': "they're",
    'theyve': "they've",
    'twas': "'twas",
    'wasnt': "wasn't",
    "we'dve": "we'd've",
    "wed've": "we'd've",
    'werent': "weren't",
    'weve': "we've",
    'whatll': "what'll",
    'whatre': "what're",
    'whats': "what's",
    'whatve': "what've",
    'whens': "when's",
    'whered': "where'd",
    'wheres': "where's",
    'whereve': "where've",
    "who'dve": "who'd've",
    'whod': "who'd",
    "whod've": "who'd've",
    'wholl': "who'll",
    'whos': "who's",
    'whove': "who've",
    'whyll': "why'll",
    'whyre': "why're",
    'whys': "why's",
    'wont': "won't",
    "wouldn'tve": "wouldn't've",
    'wouldnt': "wouldn't",
    "wouldnt've": "wouldn't've",
    'wouldve': "would've",
    "y'all'dve": "y'all'd've",
    "y'alld've": "y'all'd've",
    "y'allll": "y'all'll",
    'yall': "y'all",
    "yall'd've": "y'all'd've",
    "yall'll": "y'all'll",
    "you'dve": "you'd've",
    'youd': "you'd",
    "youd've": "you'd've",
    'youll': "you'll",
    'youre': "you're",
    'youve': "you've"
}
MANUAL_MAP = {"none": "0", "zero": "0", "one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6",
              "seven": "7", "eight": "8", "nine": "9", "ten": "10"}
ARTICLES = ("a", "an", "the")
PERIOD_STRIP = re.compile(r"(?!<=\d)(\.)(?!\d)")
COMMA_STRIP = re.compile(r"(\d)(\,)(\d)")
PUNCT = [";", r"/", "[", "]", '"', "{", "}", "(", ")", "=", "+", "\\", "_", "-", ">", "<", "@", "`", ",", "?", "!"]


def process_punctuation(text: str) -> str:
    out = text
    for mark in PUNCT:
        if (mark + " " in text or " " + mark in text) or COMMA_STRIP.search(text) is not None:
            out = out.replace(mark, "")
        else:
            out = out.replace(mark, " ")
    # The reference passes re.UNICODE (32) in the position of `count`, so at most 32 periods are removed; kept for parity.
    return PERIOD_STRIP.sub("", out, re.UNICODE)


def process_digit_article(text: str) -> str:
    words = [MANUAL_MAP.get(word, word) for word in text.lower().split()]
    words = [word for word in words if word not in ARTICLES]
    return " ".join(CONTRACTIONS.get(word, word) for word in words)


def _clean(text: str) -> str:
    return text.replace("\n", " ").replace("\t", " ").strip()


def answer_texts(answers: Iterable[Any]) -> list[str]:
    """The human answer strings, from ``{"answer": ...}`` objects or plain strings."""
    texts = []
    for item in answers:
        value = item.get("answer") if isinstance(item, dict) else item
        if not isinstance(value, str):
            raise ValueError("A human answer must be a string or an object with an 'answer' string")
        texts.append(value)
    return texts


def vqa_accuracy(candidate: str, human_answers: Sequence[str]) -> float:
    """Accuracy of one candidate answer against the human answers (0..1)."""
    if not human_answers:
        raise ValueError("VQA accuracy needs the human answers")
    truth = [_clean(answer) for answer in human_answers]
    guess = _clean(candidate)
    if len(set(truth)) > 1:
        truth = [process_digit_article(process_punctuation(answer)) for answer in truth]
        guess = process_digit_article(process_punctuation(guess))
    scores = []
    for index in range(len(truth)):
        matches = sum(1 for other, answer in enumerate(truth) if other != index and answer == guess)
        scores.append(min(1.0, matches / 3))
    return sum(scores) / len(scores)
