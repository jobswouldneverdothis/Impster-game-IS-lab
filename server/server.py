# server/server.py
# Full Flask-SocketIO backend implementing Imposter-style rounds (start, clues, voting, elimination)
# Fixed: emit role/word both private and legacy events; auto-start voting once all clues received;
# remove_player correctly mutates global votes/clues.

import eventlet
eventlet.monkey_patch()

from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_socketio import SocketIO
import os
import random
import time
import sys

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

# players: sid -> { id: sid, name: str, alive: bool, joined_at: float }
players = {}

# game runtime state
game_active = False
imposter_sid = None
roles = {}             # sid -> "imposter"|"crewmate"
secret_words = {}      # sid -> word string
alive_sids = set()
votes = {}             # voter_sid -> target_sid
clues = {}             # sid -> clue string
clues_revealed = False

# sample word pairs (crewmate_word, imposter_word)
WORD_PAIRS = [
    ("apple", "apples"),
    ("cat", "cap"),
    ("river", "rival"),
    ("book", "books"),
    ("light", "slight"),
    ("plane", "planes"),
    ("bottle", "battle"),
]

MIN_PLAYERS = 3

@app.route("/health")
def health():
    return jsonify({"status": "ok"})

def emit_player_list(to_all=True, to_sid=None):
    pdata = [{"id": sid, "name": p["name"], "alive": p["alive"]} for sid, p in players.items()]
    if to_all:
        socketio.emit("player_list", pdata)
    elif to_sid:
        socketio.emit("player_list", pdata, to=to_sid)

def emit_system_message(text):
    socketio.emit("system_message", {"text": text, "time": int(time.time())})

# Utility: safe cleanup when a sid leaves mid-round
def remove_player(sid):
    global players, alive_sids, roles, secret_words, votes, clues
    # Remove player entry
    players.pop(sid, None)
    alive_sids.discard(sid)
    roles.pop(sid, None)
    secret_words.pop(sid, None)
    # remove votes where voter==sid or target==sid (rebuild dict)
    votes = {voter: target for voter, target in votes.items() if voter != sid and target != sid}
    # remove clue if present
    clues.pop(sid, None)
    # assign back to globals explicitly (since we rebind votes variable locally)
    globals()['votes'] = votes

@socketio.on("connect")
def on_connect():
    # send current player list to connecting client
    emit_player_list(to_all=False, to_sid=request.sid)

@socketio.on("join")
def on_join(data):
    sid = request.sid
    name = (data or {}).get("name", "Anonymous")
    name = str(name).strip() or "Anonymous"

    # add or update player
    players[sid] = {"id": sid, "name": name, "alive": True, "joined_at": time.time()}
    alive_sids.add(sid)

    emit_system_message(f"{name} joined the game.")
    emit_player_list()

@socketio.on("chat_message")
def on_chat_message(data):
    if not isinstance(data, dict):
        return
    text = data.get("text", "")
    frm = data.get("from", "unknown")
    payload = {"text": text, "from": frm, "time": int(time.time())}
    socketio.emit("chat_message", payload)

@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid
    player = players.get(sid)
    if player:
        name = player.get("name")
        # remove the player and clean up round state
        remove_player(sid)
        emit_system_message(f"{name} left the game.")
        emit_player_list()
    else:
        # still try to clean state
        remove_player(sid)

# ----------------- Game flow events -----------------

@socketio.on("start_game")
def on_start_game(data):
    """
    Start game:
    - require MIN_PLAYERS
    - choose imposter
    - assign words
    - emit game_started (public)
    - emit your_role/your_word (private) AND legacy role/word events
    """
    global game_active, roles, secret_words, alive_sids, votes, clues, clues_revealed, imposter_sid

    if game_active:
        socketio.emit("game_error", {"msg": "Game already active."}, to=request.sid)
        return

    sids = list(players.keys())
    if len(sids) < MIN_PLAYERS:
        socketio.emit("game_error", {"msg": f"Not enough players (need at least {MIN_PLAYERS})."}, to=request.sid)
        return

    # initialize round
    game_active = True
    votes = {}
    clues = {}
    clues_revealed = False
    roles = {}
    secret_words = {}
    alive_sids = set(sids)

    # select imposter
    imposter_sid = random.choice(sids)

    # choose word pair
    crewmate_word, imp_word = random.choice(WORD_PAIRS)

    # assign roles and secret words
    for sid in sids:
        if sid == imposter_sid:
            roles[sid] = "imposter"
            secret_words[sid] = imp_word
        else:
            roles[sid] = "crewmate"
            secret_words[sid] = crewmate_word

    # public: game started
    socketio.emit("game_started", {"numPlayers": len(sids)})

    # private: send role and word (new events) and legacy events (role, word) for compatibility
    for sid in sids:
        # new-style private events
        socketio.emit("your_role", {"role": roles[sid]}, to=sid)
        socketio.emit("your_word", {"word": secret_words[sid]}, to=sid)
        # legacy/public-style single-client events (some clients expect these names)
        socketio.emit("role", {"role": roles[sid]}, to=sid)
        socketio.emit("word", {"word": secret_words[sid]}, to=sid)

    emit_system_message("Game started — roles and words assigned.")
    emit_player_list()

@socketio.on("submit_clue")
def on_submit_clue(data):
    """
    data: { clue: "<text>" }
    Store player's clue. When all alive players submitted, reveal clues and auto-start voting.
    """
    global clues, clues_revealed, alive_sids

    if not game_active:
        socketio.emit("game_error", {"msg": "Game not active."}, to=request.sid)
        return

    sid = request.sid
    if sid not in alive_sids:
        socketio.emit("game_error", {"msg": "You are eliminated and cannot submit clues."}, to=sid)
        return

    clue = (data or {}).get("clue", "")
    clue = str(clue).strip()[:60]
    clues[sid] = clue

    # notify that this player submitted a clue
    socketio.emit("clue_submitted", {"sid": sid, "name": players.get(sid, {}).get("name", "Unknown")})

    # If all alive submitted, broadcast all clues and auto-start voting
    if len([s for s in alive_sids if s in clues]) >= len(alive_sids):
        # Build reveal map of name -> clue
        reveal = {players.get(s, {}).get("name", s): clues.get(s, "") for s in alive_sids}
        clues_revealed = True
        socketio.emit("all_clues_revealed", {"clues": reveal})
        emit_system_message("All clues revealed — voting will start now.")
        # **AUTO-START VOTING**
        socketio.emit("voting_started", {"aliveCount": len(alive_sids)})
        emit_system_message("Voting started — please cast your votes.")

@socketio.on("start_voting")
def on_start_voting(data):
    # retained for compatibility (host-triggered), still allowed
    if not game_active:
        socketio.emit("game_error", {"msg": "Game not active."}, to=request.sid)
        return
    if not clues_revealed:
        socketio.emit("game_error", {"msg": "Clues are not revealed yet."}, to=request.sid)
        return
    socketio.emit("voting_started", {"aliveCount": len(alive_sids)})
    emit_system_message("Voting started — please cast your votes.")

@socketio.on("cast_vote")
def on_cast_vote(data):
    """
    data: { targetId: "<sid>" }
    Record vote and emit progress. When all alive players have voted → tally and emit results.
    """
    global votes, alive_sids, roles, game_active

    if not game_active:
        socketio.emit("game_error", {"msg": "Game not active."}, to=request.sid)
        return

    voter = request.sid
    if voter not in alive_sids:
        socketio.emit("game_error", {"msg": "Eliminated players cannot vote."}, to=voter)
        return

    target = (data or {}).get("targetId")
    if target not in alive_sids:
        socketio.emit("game_error", {"msg": "Invalid vote target."}, to=voter)
        return

    votes[voter] = target

    voter_name = players.get(voter, {}).get("name", "Unknown")
    target_name = players.get(target, {}).get("name", "Unknown")

    # immediate event: who voted for whom
    socketio.emit("vote_cast", {
        "voterId": voter,
        "voterName": voter_name,
        "targetId": target,
        "targetName": target_name,
        "time": int(time.time())
    })

    # voting progress
    voters_names = [players.get(v, {}).get("name", "Unknown") for v in votes.keys() if v in players]
    socketio.emit("voting_update", {
        "voters": voters_names,
        "votesCount": len(votes),
        "aliveCount": len(alive_sids)
    })

    # if all alive players have voted → tally
    if len([v for v in votes.keys() if v in alive_sids]) >= len(alive_sids):
        # Tally by sid
        tally = {}
        for t in votes.values():
            tally[t] = tally.get(t, 0) + 1

        # find max votes
        max_votes = max(tally.values())
        top_targets = [sid for sid, c in tally.items() if c == max_votes]

        # break tie randomly
        eliminated = random.choice(top_targets)
        eliminated_name = players.get(eliminated, {}).get("name", "Unknown")

        # mark eliminated
        if eliminated in alive_sids:
            alive_sids.discard(eliminated)
            if eliminated in players:
                players[eliminated]["alive"] = False

        # convert tally to name->count dictionary for friendly display
        tally_named = {players.get(k, {}).get("name", k): v for k, v in tally.items()}

        # emit results
        socketio.emit("vote_results", {
            "eliminatedId": eliminated,
            "eliminatedName": eliminated_name,
            "tally": tally_named
        })

        emit_system_message(f"{eliminated_name} was voted out.")

        # clear votes & clues for next round
        votes.clear()
        clues.clear()
        # clues_revealed reset handled by next round

        # check win condition
        remaining_roles = {sid: roles.get(sid) for sid in alive_sids}
        imposters_remaining = sum(1 for r in remaining_roles.values() if r == "imposter")
        crewmates_remaining = sum(1 for r in remaining_roles.values() if r == "crewmate")

        if imposters_remaining == 0:
            # crewmates win
            socketio.emit("game_over", {"winner": "crewmates"})
            emit_system_message("Crewmates win!")
            _reset_game_state()
            return
        if imposters_remaining >= crewmates_remaining:
            socketio.emit("game_over", {"winner": "imposter"})
            emit_system_message("Imposter wins!")
            _reset_game_state()
            return

        # otherwise continue next round: notify clients player list changed
        emit_player_list()

def _reset_game_state():
    global game_active, roles, secret_words, alive_sids, votes, clues, clues_revealed, imposter_sid
    game_active = False
    roles = {}
    secret_words = {}
    votes = {}
    clues = {}
    clues_revealed = False
    imposter_sid = None
    # reset alive flags for all players in lobby
    for sid in players:
        players[sid]["alive"] = True
    alive_sids.clear()
    alive_sids.update(players.keys())
    emit_player_list()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5050))
    print("Starting server on 0.0.0.0:%d" % port, file=sys.stderr)
    socketio.run(app, host="0.0.0.0", port=port, use_reloader=False)
