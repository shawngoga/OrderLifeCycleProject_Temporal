## 1. Project Description

This project implements a reproducible, event-driven order lifecycle system using Temporal workflows, FastAPI, and SQLAlchemy. It is designed for local development on Windows using PowerShell and Python, with strict boundaries, audit-friendly logging, and manual environment setup (no Docker).


This project simulates an order life cycle with 8 stages:
1. Order received
2. Order validated
3. Order manually reviewed
4. Payment charged
5. Package prepared
6. Carrier dispatched
7. Order shipped
8. Order received

It leverages Temporal to achieve idempotency of the code flow, ensuring retries are safe, workflows complete reliably, and database writes remain consistent.

------------------------------------------------------------------------------

## Start Instructions

### Setting up the environment
On Windows:
1. Open PowerShell as Administrator.
2. Run:
   Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope Process
   .\bootstrap.ps1

This script configures the .env file, sets up the Temporal server, prepares the Python environment, and ensures no duplicate downloads by checking permissions first.

### Starting the API
3. Run:
    In powershell run: 
    .\start
    This starts the API. Access Swagger UI at: http://localhost:8000/docs

---------------------------------------------------------------------------------- 

## Functionalities Testing

### 1. Start Temporal server
## start-server
    This initiates the Temporal server along with:

    Order Workflow

    Shipping Child Workflow

    Returns Workflow

### 2. Start a new order (start-order)
    Orders are auto-incremented in the DB. Provide a delivery address. Performance logic:

    To meet the 15-second ceiling without hard termination:

        - Very fast timeouts terminate flaky calls immediately, triggering retries.
        - Hedging logic runs multiple concurrent attempts per stage; the first success proceeds, others are canceled. This reduced average completion time from ~40s to ~10s, with 99%+ finishing under 15s.

    Optional: To test Temporal retries without hedging, edit hedge_state.py, line 41:
        - async def run_with_hedges(fn, *args, hedges: int = 7, **kwargs): 
        - Setting int =1 forces single-stream execution, showing Temporal’s retry/idempotency behavior but will sacrifice the 15 sec limit.

### 3. Update address
    Update JSON with order_id and new address. Rejected if the order has reached the dispatched stage.

### 4. Cancel order
    Before payment_charged → immediate cancel

    After payment_charged but before shipping → refund issued, cancellation upheld

    At shipping stage → cancellation rejected

### 5. Return order
    Provide the order_id.

    If shipped within 5 minutes → return accepted, refund issued

    If older than 5 minutes → return rejected

### 6. Get order stage
    Query the current workflow stage by order_id.

### 7. DB dump
    Prints contents of Orders, Payments, and Events tables. Useful for verifying cancellations, returns, and updates.

### 8. Test cancel order
    Runs a workflow that creates and cancels an order randomly within 6s. Observe how cancel signals propagate. 
    Helpful since most workflows will complete in under 10s. Run this a few times to test the cancel signal behaviour thorougly 


### 9. Test update address
    Runs a workflow that creates and updates an order’s address randomly within 6s. Observe how update signals propagate.
    Helpful since most workflows will complete in under 10s. Run this a few times to test the cancel signal behaviour thorougly

---------------------------------------------------------------------------

## Code Structure
Code
function_stubs/       # Flaky functions + DB read/write logic
activities/           # Orchestration layer for function stubs
workflows/
  ├─ order_workflow.py     # Order workflow logic
  ├─ shipping_workflow.py  # Shipping workflow logic
  └─ return_workflow.py    # Return workflow logic
hedge_state.py        # Hedging logic for concurrent retries
signals.py            # Signal handling logic
workers/
  ├─ order_worker.py
  ├─ shipping_worker.py
  └─ returns_worker.py
main.py               # API entrypoint


------------------------------------------------------------
### 5. Key Notes

Idempotency: Temporal ensures retries don’t cause duplicate DB writes.

Hedging: Multiple concurrent attempts per stage reduce latency.

Signals: Allow runtime updates (address changes, cancellations).

Returns Workflow: Demonstrates refund logic with time-based acceptance/rejection.