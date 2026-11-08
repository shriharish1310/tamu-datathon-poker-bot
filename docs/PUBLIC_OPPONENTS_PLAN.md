# Public opponent screen

This research branch leaves the submitted default branch and strategy untouched.
Starfish is frozen at `6e5b590bc922f047de670efdd5fd599f7459a75d`.
The 78 opponent default-branch revisions were pinned before any result in
`experiments/PUBLIC_OPPONENTS_LOCK.json`.

Each compatible repository receives one full official 1,000-deal duplicate
match (2,000 hands), with identical seed, swapped seats and fresh processes.
Six independent Actions runners each process 13 opponents sequentially. This
does not run scored matches concurrently on one host.

External bots use the trusted organizer Dockerfile, declared dependencies,
non-root execution, one CPU, 4 GiB, a read-only filesystem and isolated network
namespace without external connectivity. The official judge shares only the
local namespace. External source is never imported or executed on the host.
Source manifests, identities, raw half/match JSON, reliability diagnostics and
build/runtime failures are retained. External setup scripts and Dockerfiles
are not executed; submodules and Git LFS are not implicitly installed.

Root entry points are preferred. An unambiguous nested entry point may be
tested with its subdirectory explicitly recorded. Missing dependencies,
ambiguous entry points, unavailable artifacts, and startup failures are
compatibility exclusions, not strategic wins. Opponent forfeits are separated
from wins against functioning policies. Internal opponent counters may be
unavailable even when the judge reports no errors.

One seed is a broad screen, not a precise strength ranking. Close verdicts,
particularly isolated wins and losses, require independent confirmation.
Results measure publicly pinned revisions, not confirmed organizer submissions.

No tuning, opponent strategy edits, or candidate `3e36f20` changes are included.
