import chess
import chess.svg
import requests
import json
import subprocess

# Load the configuration from the JSON file
with open('config.json', 'r') as config_file:
    config = json.load(config_file)

# Access configuration values
folder = config['folder']
nibbler = config['nibbler']
limit_min_move = config['limit_min_move']
liurl_base = config['liurl_base']
liurl_speed = config['liurl_speed']
liurl_ratings = config['liurl_ratings']
liurl_moves = config['liurl_moves']
liurl_topGames = config['liurl_topGames']
liurl_recentGames = config['liurl_recentGames']
liurl = f"{liurl_base}?speeds={liurl_speed}&ratings={liurl_ratings}&moves={liurl_moves}&topGames={liurl_topGames}&recentGames={liurl_recentGames}"

# Initiate chessboard
board = chess.Board()

def CastlingUci(move):
    if move not in ["e1a1", "e1h1", "e8a8", "e8h8"]:
        return(move)
    else:
        table = {"e1a1": "e1c1",
                "e1h1": "e1g1",
                "e8a8": "e8c8",
                "e8h8": "e8g8"}
        move = table[move]
        return(move)

def LegalMoves(fen):
    legal = []
    board = chess.Board(fen)
    for x in board.legal_moves:
        legal.append(str(x))
    return(legal)

def LegalToSan(board):
    san_list = ""
    for x in LegalMoves(board.fen()):
        san_list = san_list + board.san(board.parse_uci(x)) + " "
    return(san_list)

def CreateBranch(fen, line, score):
    r = requests.get(liurl + fen)
    legal = LegalMoves(fen)
    new_branch = {fen: {"line": line, "branch": {"moves": [], "scores": []}}}
        
    for x in r.json()["moves"]:
        y = CastlingUci(x["uci"])
        legal.remove(y)		
        nm = x["white"]+x["draws"]+x["black"]
        new_branch[fen]["branch"]["moves"].append(y)
        new_branch[fen]["branch"]["scores"].append(int(nm))

    new_branch[fen]["branch"]["scores"] = CalcScore(new_branch[fen]["branch"]["scores"], score)

    # Search for transposition
    transposition = False
    for position in mydb:
        if fen.split(" ")[0] == position.split(" ")[0] and fen.split(" ")[1] == position.split(" ")[1]:
            transposition = position
            print("\nYou have T-R-A-N-S-P-O-S-E-D in an earlier trained position.\n")

    # Because we have always selected the highest score move before,
    # let's delete the new one that will have a lowest score.
    # We also use this process to delete position that have reach the LIMIT of total resulting position
    if transposition == False and new_branch[fen]["branch"]["scores"] != "limit":
        mydb[fen] = new_branch[fen]
    # But, we also have to add the transposed score to the old score,
    # because now the position is more likely to be reached.
    if transposition == True:
        for move in mydb[transposition]["branch"]["moves"]:
            index_of_old = mydb[transposition]["branch"]["moves"].index(move)
            index_of_same = new_branch[fen]["branch"]["moves"].index(move)

            old_score = mydb[transposition]["branch"]["scores"][index_of_old]
            trans_score = new_branch[fen]["branch"]["scores"][index_of_same]
            new_result = old_score + trans_score

            mydb[transposition]["branch"]["scores"][index_of_old] = new_result

    # Dumping new branch (or new score eval for transposed position)	
    json_file = open(folder + "db.json", "w")		
    json.dump(mydb, json_file)
    json_file.close()

def CalcScore(list_score, score):
    totmove = 0
    per_score = []
    
    for x in list_score:
        totmove += x
    for y in list_score:
        per_score.append(round(y / totmove * score, 7))		
        
    # Informing on the number of games played in the resulting var
    print("\nThe resulting position have a total of", totmove, "games played in the DB.\n")

    # Stop the branch if total resulting positions in DB is < to the configuration: limit_min_move	
    if totmove < limit_min_move:
        per_score = "limit"
        input("\n### The LIMIT of 10 total resulting positions as been reached. The branch as been deleted ###\n(type anything to continue)")

    return per_score

def NextMove():

    # Delete empty positions: where every potential move has been explored.
    to_delete = []
    for dict in mydb:
        if not mydb[dict]["branch"]["scores"]:
            to_delete.append(dict)
            print("We've deleted this entry:")
            print(dict)
            print("All the possible move were already explored.\n\n")
    for element in to_delete:
        del mydb[element]

    # Find highest score
    highest = []
    for dict in mydb:
        try:
            highest.append(max(mydb[dict]["branch"]["scores"]))
        except:
            print(dict, mydb[dict])
            print("!! !! !! Error in the process to find HIGHEST score !! !! !!")

    highest = max(highest)

    for dict in mydb:
        if highest in mydb[dict]["branch"]["scores"]:
            fen = dict
            line = mydb[dict]["line"]
            highest = mydb[dict]["branch"]["scores"].index(highest)
            move = mydb[dict]["branch"]["moves"][highest]
            score = mydb[dict]["branch"]["scores"][highest]
            break

    del mydb[fen]["branch"]["moves"][highest]
    del mydb[fen]["branch"]["scores"][highest]

    board = chess.Board(fen)
    board.push_uci(move)
    fen = board.fen()
    line = line + [move]

    if board.turn == True:
        print(	"\nwwwwwwwwwwwwwwwwwwwwwwww\n" + 
                "WWW WHITE repertoire WWW\n" + 
                "wwwwwwwwwwwwwwwwwwwwwwww\n")
    else:
        print(	"\nbbbbbbbbbbbbbbbbbbbbbbbb\n" + 
                "BBB BLACK repertoire BBB\n" + 
                "bbbbbbbbbbbbbbbbbbbbbbbb\n")

    print("\nNext move to study is:\n",
    chess.Board().variation_san([chess.Move.from_uci(m) for m in line]),
    "<--- with a score of:", round(score * 100, 2), "%")
    print("\n\nList of legal response:\n")
    print(LegalToSan(board))

    # open nibbler with loaded pgn
    with open("temp.pgn", "w+") as pgn_file:
        pgn_file.writelines(chess.Board().variation_san([chess.Move.from_uci(m) for m in line]))
    subprocess.call([nibbler, "temp.pgn"])

    choice = input("\nYour move?\n")	
    choice = board.uci(board.parse_san(choice))
    board.push_uci(choice)

    CreateBranch(board.fen(), line + [choice], score)

try:
    json_file = open(folder + "db.json", "r")
    mydb = json.load(json_file)
except:
    json_file = open(folder + "db.json", "w+")
    mydb = {}
    print(LegalToSan(board))
    first = input("\nWhat is your first move for white?\n")
    first = board.uci(board.parse_san(first))
    CreateBranch(board.fen(), [], 1)
    board.push_uci(first)
    CreateBranch(board.fen(), [first], 1)

json_file.close()

NextMove()
