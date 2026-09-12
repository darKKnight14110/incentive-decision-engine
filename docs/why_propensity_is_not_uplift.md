# Why propensity is not uplift

An outcome propensity estimates `P(Y=1 | X)`: who is likely to convert. Uplift
estimates `E[Y(1) - Y(0) | X]`: who converts because of the intervention.

Targeting high propensity users can spend budget on sure things whose order was
going to happen anyway. It can also miss persuadables and cannot reliably find
negative-response users. The propensity model is therefore retained as a
transparent incumbent baseline and evaluated with calibration and predictive
metrics, while policy choice is evaluated with randomized held-out value.
