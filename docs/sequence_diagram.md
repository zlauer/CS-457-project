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
