# Message Protocol:

**Connect:** Client requests to join game with player alias.

Player 1.
```{
  "msg_type": "CONNECT",
  "player_id": "Player_1",
  "payload": {
    "row": 0,
    "col": 2
  },
  "timestamp": 1727000000
}
```
---
**Lobby_Wait:** Server notifies Client 1 that it is waiting for Player 2 to connect.
```{
  "msg_type": "LOBBY_WAIT",
  "player_id": "Player_1",
  "payload": {
    "row": 0,
    "col": 2
  },
  "timestamp": 1727000000
}
```
---
**Game_Start:** Server notifies both clients that game has started and assigns roles (Player 1 / Player 2).
```
{
  "msg_type": "GAME_START",
  "player_id": "Player_1",
  "payload": {
    "row": 0,
    "col": 2
  },
  "timestamp": 1727000000
}
```
---
**Move:** Ative player submits move coordinates or answer selection.
```
{
  "msg_type": "MOVE",
  "player_id": "Player_1",
  "payload": {
    "row": 0,
    "col": 2
  },
  "timestamp": 1727000000
}
```
---
**State_Update:** Server broadcasts updated board state, scores, and active player turn.
```
{
  "msg_type": "STATE_UPDATE",
  "player_id": "Player_1",
  "payload": {
    "row": 0,
    "col": 2
  },
  "timestamp": 1727000000
}
```
---
**Error:** Server notifies client of out-of-turn move, invalid coordinates, or malformed message.
```
{
  "msg_type": "ERROR",
  "player_id": "Player_1",
  "payload": {
    "row": 0,
    "col": 2
  },
  "timestamp": 1727000000
}
```
---
**Disconnect:** Client notifies server of intentional departure/quit.
```
{
  "msg_type": "DISCONNECT",
  "player_id": "Player_1",
  "payload": {
    "row": 0,
    "col": 2
  },
  "timestamp": 1727000000
}
```
---
**Game_Over:** Server broadcasts final game outcome (Winner / Draw / Forfeit) and final scores.
```
{
  "msg_type": "GAME_OVER",
  "player_id": "Player_1",
  "payload": {
    "row": 0,
    "col": 2
  },
  "timestamp": 1727000000
}
```

# Wirestream Example
```
{"msg_type":"CONNECT","player_id":"Alice","timestamp":1727000000}\n
{"msg_type":"MOVE","player_id":"Alice","payload":{"row":0,"col":2},"timestamp":1727000005}\n
```
