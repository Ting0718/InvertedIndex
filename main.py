#TOTAL_DOCUMENTS = 55392
#TOAL_TOKENS = 1256389
import os
import nltk
from nltk.stem import PorterStemmer
import json
from bs4 import BeautifulSoup
import tokenizer
from collections import defaultdict
import threading
import indexer
import simhash
import search
import math

#constants
MAX_INDEX_LENGTH = 15000  # max length of indexes before merge
THREADS = 1  # how many threads will be used to scan documents
TOTAL_DOCUMENTS = 51187  # how many docs in total


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
        self.simhashes = simhash.HashManager(0.95)

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
    '''porter stemmer'''
    porter = PorterStemmer()
    return (porter.stem(s))


def readFiles(mypath: str):
    '''parses through all files in the folder and returns a list of their file paths'''
    filepaths = []
    for root, dirs, files in os.walk(mypath, topdown=True):
        for name in files:
            filepaths.append(os.path.join(root, name))
    return filepaths


def parseFiles(filename: str):
    ''' Reads through the corpus '''
    f = open(filename, 'r', encoding="utf-8", errors="ignore")
    content = json.load(f)

    url = content["url"]
    html = content["content"]  # splits the content fromurl

    soup = BeautifulSoup(html, "lxml")
    output = tokenizer.tokenize(soup.get_text())  # tokenizes the output
    return url, output


def writeFile(inverted_index: dict, filename: str):
    '''Writes parsed information into a disk'''
    f = open(filename, "w")
    for k, v in sorted(inverted_index.items()):
        f.write(k + "," + ",".join(str(x[0]) + " " + str(x[1])
                                   for x in sorted(v, key=lambda x: x[0])) + "\n")
    f.close()


def merge(list1, list2):
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
    ''' Merging files '''
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


'''Code no longer needed for optimization'''
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
    '''Creates a json file containing every 20th term and a offset value to the to the function'''
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


def tf(tokenized_file: [str]):
    ''' calculate the tf and return as a list of tuples of (term,frequency) '''
    terms = defaultdict(int)
    for t in tokenized_file:
        stemWord = porterstemmer(t)
        terms[stemWord] += 1
    to_ret = []
    for k, v in terms.items():
        to_ret.append((k, v))
    return to_ret


def tf_as_dict(tokenized_file: [str]):
    ''' calculate the tf and return as a dictionary'''
    terms = defaultdict(int)
    for t in tokenized_file:
        stemWord = porterstemmer(t)
        terms[stemWord] += 1
    return terms


def idf(term: str):  # need to write to output.txt????
    file = "outputs/output" + term[0] + ".txt"
    '''IDF(t) = log_10(Total number of documents / Number of documents with term t in it).'''
    try:
        num_of_doc = 0
        with open(file, 'r') as f:
            for line in f:
                if search.getToken(line) == porterstemmer(term):
                    num_of_doc = len(search.SetOfDocId(line))
                    break

        # round to only 3 decimals to save spaces
        return round(math.log10(TOTAL_DOCUMENTS/num_of_doc), 3)
    except:
        return 0  # there is no such term || the length is zero


def tf_idf(url, tokenized_file: [str]):
    '''return a list that the first element = the url, and second = a list of tf_idf'''
    d = [url, []]
    for t in (tokenized_file):
        d[1].append(round(tf_as_dict(tokenized_file)[t] * idf(t), 3))
    return d


if __name__ == "__main__":
    #path = "/Users/Scott/Desktop/DEV"
    #path = "/Users/shireenhsu/Desktop/121_Assignment3/DEV"
    #path = "/Users/jason/Desktop/ANALYST"

    #Actually reading the JSON and merging the files into one output.txt

    # path = input("Enter Path Name: ")

    # files = readFiles(path)
    # doc_id = DocID()
    # manager = IndexerManager(doc_id, files)
    # get_doc_lock = threading.Lock()
    # simhash_lock = threading.Lock()
    # indexers = [indexer.Indexer("partial(thread" + str(i) + ").txt", manager, #creates and instntiates indexers based on THREADS constant
    #                             get_doc_lock, simhash_lock, i) for i in range(1, THREADS+1)]
    # for indexer in indexers:
    #     indexer.start() #starts all indexer threads
    # for indexer in indexers:
    #     indexer.join() #waits for all indexer threads
    # mergeFiles(manager.partial_indexes)
    # doc_id.write_doc_id("docID.json")
    #indexIndex("output.txt", "indexindex.json")

    tokens = parseFiles(
        "/Users/shireenhsu/Desktop/CS121/Assignment3/121_Assignment3/DEV/alderis_ics_uci_edu/0f274aaa945c05641a9677b951c32026bb201ec9aeb6e691fedd1235b3a5d6af.json")

    tf_idf(tokens[0], tokens[1])
    
   
    
