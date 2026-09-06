# V0.3 v9.10 freeze and seal lifecycle implementation plan

## Task 1: Register lifecycle contracts

Add T-CX241–T-CX244 once to the contextual test plan and add preservation
language to the contextual contract. Do not change product semantics.

## Task 2: Prove development compatibility

Run deterministic qualification and calibration into an ignored audit
directory. Compare their semantic payloads with the frozen reports while
ignoring only run-specific code identity. Add a failing T-CX241 test, append one
amendment row with the current implementation SHA and audit hashes, then make
the test pass.

## Task 3: Retire v3 from active execution

Add failing T-CX242/T-CX243 tests. Append accurate v9.9 execution state to the
supersession record: 47/60 original terminal slots, infrastructure stop, 13/13
diagnostic-only continuation, original confirmation incomplete, and no active
seal. Update preflight to reject non-active v3 before credentials or executor
construction. Never modify v3 seal files or either run directory.

## Task 4: Cumulative verification

Run the focused lifecycle tests, v9.10 focused suite, full pytest, Ruff, mypy,
architecture/preservation, diff check, wheel smoke, and the CPython 3.11/3.12
matrix. Update the acceptance report with exact evidence. Stop without model
calls, final-test access, commit, or push.
