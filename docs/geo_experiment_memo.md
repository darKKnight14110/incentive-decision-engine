# Geographic validation memo

User-level randomization is insufficient once offers change city-hour demand,
delivery times, and availability for untreated users. Validate capacity-aware
policies with city or hour clusters randomized to policy versus control. Size
the test using the baseline rate, cluster size, and intra-cluster correlation;
the design effect is `1 + (m - 1) * ICC`.

The short-run experiment estimates operational spillovers. It does not by
itself identify long-run equilibrium effects such as merchant entry or courier
repositioning.
