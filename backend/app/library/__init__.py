"""HTTP-only library client and helpers.

All real library endpoints live in this package. Mutation endpoints
(:py:meth:`LibraryClient.submit_reservation`, :py:meth:`cancel_reservation`,
:py:meth:`check_in`, :py:meth:`renew`) are guarded by
``Settings.allow_mutation_test`` and refuse to run when the flag is off.
"""
