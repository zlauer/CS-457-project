```mermaid
stateDiagram-v2
    direction TB

    [*] --> AwaitMove

    state "Await shot request" as AwaitMove
    state "Validate move" as ValidateMove
    state MoveValid <<choice>>
    state "Send rejection to requesting client" as RejectMove
    state "Resolve hit, miss, or sunk ship" as ResolveShot
    state "Update shooter's score" as UpdateScore
    state "Switch active player" as SwitchTurn
    state "Broadcast result, scores, and next player" as BroadcastUpdate

    AwaitMove --> ValidateMove: either client sends a shot
    ValidateMove --> MoveValid
    MoveValid --> RejectMove: invalid
    RejectMove --> AwaitMove: keep turn, board, and scores unchanged
    MoveValid --> ResolveShot: valid
    ResolveShot --> UpdateScore: record shot on board
    UpdateScore --> SwitchTurn: score updated
    SwitchTurn --> BroadcastUpdate: select the other computer
    BroadcastUpdate --> AwaitMove: send update to both clients

    note right of ValidateMove
        Requester must be the active player.
        Target must be on the board.
        Target must not have been fired on before.
    end note

    note right of UpdateScore
        Track hits and ships sunk.
        A miss leaves the score unchanged.
    end note
```

Within this presented diagram, there are both validations of movements and rejections of movements.  These include within the realm of a player selecting a spot outside of their own turn, and then subsequently throwing out that turn.

---
Here is an updated version of the specification diagram featuring these movements:

```mermaid
stateDiagram-v2
    direction TB

    [*] --> WaitingForPlayers
    WaitingForPlayers --> PlacingShips: both computers connected
    WaitingForPlayers --> Cancelled: connection timeout

    PlacingShips --> Player1Turn: both fleets valid and locked
    PlacingShips --> PlacingShips: invalid fleet placement\n(overlap, out of bounds, wrong ship count)
    PlacingShips --> Reconnecting: either computer disconnects

    state Player1Turn {
        direction TB
        [*] --> AwaitP1Shot
        AwaitP1Shot --> ValidateP1Shot: shot request received
        ValidateP1Shot --> ResolveP1Shot: correct player, current turn\nand new target on board
        ValidateP1Shot --> RejectP1Shot: invalid or out-of-turn request
        RejectP1Shot --> AwaitP1Shot: send error to requester\nkeep turn and score unchanged
        ResolveP1Shot --> UpdateP1Score: record hit, miss, or sunk ship
        UpdateP1Score --> CheckP2Fleet: update hits and ships sunk
        CheckP2Fleet --> SwitchToP2: fleet still afloat
        SwitchToP2 --> BroadcastP1Update: set active player to Computer 2
        BroadcastP1Update --> [*]: send result, scores, and active player\nto both clients
        CheckP2Fleet --> BroadcastP1Win: final ship sunk
    }

    state Player2Turn {
        direction TB
        [*] --> AwaitP2Shot
        AwaitP2Shot --> ValidateP2Shot: shot request received
        ValidateP2Shot --> ResolveP2Shot: correct player, current turn\nand new target on board
        ValidateP2Shot --> RejectP2Shot: invalid or out-of-turn request
        RejectP2Shot --> AwaitP2Shot: send error to requester\nkeep turn and score unchanged
        ResolveP2Shot --> UpdateP2Score: record hit, miss, or sunk ship
        UpdateP2Score --> CheckP1Fleet: update hits and ships sunk
        CheckP1Fleet --> SwitchToP1: fleet still afloat
        SwitchToP1 --> BroadcastP2Update: set active player to Computer 1
        BroadcastP2Update --> [*]: send result, scores, and active player\nto both clients
        CheckP1Fleet --> BroadcastP2Win: final ship sunk
    }

    Player1Turn --> Player2Turn: turn update broadcast
    Player2Turn --> Player1Turn: turn update broadcast
    BroadcastP1Win --> Player1Wins: send final result, scores, and winner\nto both clients
    BroadcastP2Win --> Player2Wins: send final result, scores, and winner\nto both clients

    Player1Turn --> Reconnecting: either computer disconnects
    Player2Turn --> Reconnecting: either computer disconnects

    state Reconnecting {
        direction TB
        [*] --> AwaitReconnect
        AwaitReconnect --> ResumeTurn: both computers reconnect\nbefore grace period ends
        AwaitReconnect --> Player1Forfeits: Computer 1 remains disconnected
        AwaitReconnect --> Player2Forfeits: Computer 2 remains disconnected
        ResumeTurn --> [*]: restore board and saved turn
    }

    Reconnecting --> Player1Turn: restore saved Computer 1 turn
    Reconnecting --> Player2Turn: restore saved Computer 2 turn

    Player1Forfeits --> Player2Wins
    Player2Forfeits --> Player1Wins
    Player1Wins --> Completed
    Player2Wins --> Completed
    Completed --> [*]
    Cancelled --> [*]

    classDef turnProcessing fill:#f5f3ff,stroke:#8b5cf6,color:#4c1d95,stroke-width:2px
    class AwaitP1Shot,ValidateP1Shot,RejectP1Shot,ResolveP1Shot,UpdateP1Score,SwitchToP2,BroadcastP1Update,BroadcastP1Win turnProcessing
    class AwaitP2Shot,ValidateP2Shot,RejectP2Shot,ResolveP2Shot,UpdateP2Score,SwitchToP1,BroadcastP2Update,BroadcastP2Win turnProcessing
```
