
import os
import nltk
from nltk.stem import PorterStemmer
import json
from bs4 import BeautifulSoup
from collections import defaultdict
import threading
import tokenizer #self made
import indexer #self made
import simhash #self made
import search
import math
import re


#constants
MAX_INDEX_LENGTH = 15000  # max length of indexes before dumping to partial index
THREADS = 1  # how many threads will be used to scan documents

class DocID:
    '''
    class to keep track of document Id numbers
    Add to docs will add a document to a local dictionary of id:url and will return the id number used for that url
    '''
    def __init__(self):
        self.current_doc = 0
        self.doc_ids = dict()

    def add_to_docs(self, url: str):
        '''Assigns a doc_id to a url and adds it to the doc_ids dictionary then returns the id number assigned'''
        self.doc_ids[self.current_doc] = url
        self.current_doc += 1
        return self.current_doc - 1

    def write_doc_id(self, filename="docid.json"):
        '''writes the content of docId dictionary to a json file'''
        with open(filename, 'w') as out:
            json.dump(self.doc_ids, out)


class IndexerManager:
    '''
    class to manage indexer threads, contains simhash manager, a list of partial indexes and a document id tracker
    also contains the current url numerically indexed
    '''

    def __init__(self, doc_id_track, files):
        self.current_url = 0
        self.doc_id_tracker = doc_id_track
        self.files = files
        self.partial_indexes = []
        self.simhashes = simhash.HashManager(0.90)

    def id_index(self, document):
        '''adds doc from a thread to the id tracker'''
        return self.doc_id_tracker.add_to_docs(document)

    def request_document(self):
        '''method to be called by thread to get a new url, returns the url content'''
        if self.current_url < len(self.files):
            self.current_url += 1
            page = self.files[self.current_url-1]
            return page  # returns docContent
        else:
            return False

    def docid_file_to_url(self, url):
        '''helper method to replace the file in docid manager with the url to avoid opening file twice'''
        return self.doc_id_tracker.add_to_docs(url)

    def add_partial_index(self, index):
        ''' adds the filename of a written partial index to partial index list'''
        self.partial_indexes.append(index)

    def check_simhash(self, text):
        '''calculate and check whether there is a near duplicate of the text'''
        hashed_doc = simhash.calculate_hash(text)
        if self.simhashes.find_near_duplicate(hashed_doc):
            return True
        else:
            self.simhashes.add(hashed_doc)
            return False

def porterstemmer(s: str):
    '''stems the parameter s into its stem EG: fishes -> fish'''
    porter = PorterStemmer()
    return (porter.stem(s))


def readFiles(mypath: str):
    '''parses through all files in the folder path and returns a list of their file paths'''
    filepaths = []
    for root, dirs, files in os.walk(mypath, topdown=True):
        for name in files:
            filepaths.append(os.path.join(root, name))
    return filepaths


def parseFiles(filename: str):
    '''
    reads the file passed as an argument, returns the url, a list of tokens, and a list of tokens in headers
    or in bold
    '''
    f = open(filename, 'r', encoding="utf-8", errors="ignore")
    content = json.load(f)

    url = content["url"]
    html = content["content"]  # splits the content from url

    soup = BeautifulSoup(html, "lxml")
    output = tokenizer.tokenize(soup.get_text())  # tokenizes the output
    importants = parseFiles_important(html)
    f.close()
    return url, output, importants

def parseFiles_important(html:str):
    '''creates and returns a list of tokens found in headers, bold, and emphasis'''
    soup = BeautifulSoup(html, "lxml")

    '''a list of head tag tokens (this one includes stop words)'''
    heads = soup.find_all(re.compile('head'))
    list_of_heads = tokenizer.tokenize(" ".join([head.get_text() for head in heads]))

    '''a list of heading tag tokens'''
    headers = soup.find_all(re.compile('^h[1-6]$'))
    list_of_headers = tokenizer.tokenize_remove_stopwords(" ".join([header.get_text() for header in headers]))
    
    '''a list of title tokens (this one includes stop words)'''
    titles = soup.find_all(re.compile('title'))
    list_of_titles = tokenizer.tokenize(" ".join([title.get_text() for title in titles]))

    '''a list of bold'''
    bolds = soup.find_all(re.compile('b'))
    list_of_bolds = tokenizer.tokenize_remove_stopwords(" ".join([bold.get_text() for bold in bolds]))

    '''a list of strong'''
    strongs = soup.find_all(re.compile('strong'))
    list_of_strongs = tokenizer.tokenize_remove_stopwords(" ".join([strong.get_text() for strong in strongs]))

    '''a list of emphasis tags'''
    emphasis = soup.find_all(re.compile('em'))
    list_of_emphasis = tokenizer.tokenize_remove_stopwords(" ".join([empha.get_text() for empha in emphasis]))


    return list_of_heads+ list_of_headers + list_of_titles+ list_of_bolds + list_of_strongs + list_of_emphasis


def writeFile(inverted_index: dict, filename: str):
    '''writes each entry in the index into a file that can be used as a partial index'''
    f = open(filename, "w")
    for k, v in sorted(inverted_index.items()):
        f.write(k + "," + ",".join(str(x[0]) + " " + str(x[1]) for x in sorted(v, key=lambda x: x[0])) + "\n")
    f.close()


def merge(list1, list2):
    '''
    merges the 2 lists passed while keeping alphabetical order
    used when merging partial indexes into final index
    '''
    answer = []
    c1, c2 = 0, 0
    while(c1 < len(list1) and c2 < len(list2)):
        if list1[c1] == list2[c2]:
            answer.append(list1[c1])
            c1 += 1
            c2 += 1
        elif list1[c1] < list2[c2]:
            answer.append(list1[c1])
            c1 += 1
        else:
            answer.append(list2[c2])
            c2 += 1
    return answer + list1[c1:] + list2[c2:]


def mergeFiles(partialIndexes: list):
    '''merges all partial indexes (paths passed as argument) into one final index named output.txt'''
    Index = []  # The current line of the index corresponding to the partial index. "False" if line empty
    fileStorage = []
    for x in partialIndexes:
        files = open(x, 'r')
        # reads the first line for every file
        Index.append(files.readline().rstrip().split(","))
        fileStorage.append(files)
    #print(Index)
    #print(fileStorage)
    with open('output.txt', "w") as output:
        def allFalse():
            for x in Index:
                if x != False:
                    return True
            return False
        while(allFalse()):  # while there are still valid lines in the files
            #Find the smallest alphabetical index word
            smallest = "zzzzzzzzzzzzzzz"
            for x in Index:
                if(x):  # If x isn't False
                    smallest = smallest if smallest < x[0] else x[0]
            #If the thing is a smallest
            toWrite = []
            word = ""
            for i in range(len(Index)):
                if(Index[i] != False and Index[i][0] == smallest):
                    word = Index[i][0]
                    toWrite = merge(Index[i][1:], toWrite)
                    #Gets the next value
                    Index[i] = fileStorage[i].readline()
                    if(Index[i] == ""):
                        Index[i] = False
                    else:
                        Index[i] = Index[i].rstrip().split(",")
            #writing to file
            toWrite.insert(0, word)
            s = ",".join(toWrite) + '\n'
            output.write(s)

    for files in fileStorage:
        files.close()


# **Code no longer needed for optimization**
# def splitFiles(filename:str):
#     '''Splitgs the main output.txt into other smaller text files and puts those file names into a dictionary which it returns.'''
#     split = ["9",'a','b','c','d','e','f','g','h','i','j','k','l','m','n','o','p','q','r','s','t','u','v','w','x','y','z']
#     cursor = 0
#     #creates 27 files
#     fileStorage = []
#     for x in split:
#         open(f"outputs/output{x}.txt" , 'w')
#         fileStorage.append(open(f"outputs/output{x}.txt" , 'a'))
#     with open(filename,"r") as f:
#         for line in f:
#             #print(f"{cursor}: {line}")
#             character = line[0]
#             if character > split[cursor]:
#                 cursor += 1
#             fileStorage[cursor].write(line)

def indexIndex(filename: str, outputname: str):
    '''
    Creates a json file containing every 20th term and a offset value to the to the function
    number could be increased or decreased if time-space tradeoffs are needed
    '''
    indexer = {}
    counter = 0
    with open(filename, 'r') as f:
        for line in iter(f.readline, ''):
            if counter == 19:
                offset = f.tell()
                line = line.split()
                indexer[line[0]] = offset
                counter = 0
            else:
                counter += 1
    with open(outputname, 'w') as f:
        json.dump(indexer, f)


def tf(tokenized_file: [str],important_tokens: [str]):
    '''
    calculates the tf of a tokenized file and returns as a list of tuple(docID,tf)
    :param tokenized_file: file as a list of tokens
    :param important_tokens: list of important terms in the file
    '''
    terms = defaultdict(int)
    for t in tokenized_file:
        stemWord = porterstemmer(t)
        terms[stemWord] += 1
    for t in important_tokens:
        stemWord = porterstemmer(t)
        terms[stemWord] += 10
    to_ret = []
    for k, v in terms.items():
        to_ret.append((k, v)) #adds the term and the tf for each doc term
    return to_ret



if __name__ == "__main__":
    #path = "/Users/Scott/Desktop/DEV"
    #path = "/Users/shireenhsu/Desktop/121_Assignment3/DEV"
    #path = "/Users/jason/Desktop/ANALYST"

    #Actually reading the JSON and merging the files into one output.txt
    
    path = input("Enter Path Name: ")

    files = readFiles(path)
    doc_id = DocID()
    manager = IndexerManager(doc_id, files)
    get_doc_lock = threading.Lock() #locks for multithreading
    simhash_lock = threading.Lock()
    indexers = [indexer.Indexer("partial(thread" + str(i) + ").txt", manager, #creates and instntiates indexers based on THREADS constant
                                get_doc_lock, simhash_lock, i) for i in range(1, THREADS+1)]
    for indexer in indexers:
        indexer.start() #starts all indexer threads
    for indexer in indexers:
        indexer.join() #waits for all indexer threads
    mergeFiles(manager.partial_indexes) #merges the partial indexes written by indexers to the manager
    doc_id.write_doc_id("docID.json") #stores the docID dictionary for use later
    indexIndex("output.txt", "indexindex.json") #creates an index of the index for optimized search times


    
   
    
