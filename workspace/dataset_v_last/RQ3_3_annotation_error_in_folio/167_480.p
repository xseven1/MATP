% (1) if you go somewhere by train, you will not lose time.
% ∀x (train(x) → ¬losetime(x))
fof(premise_1, axiom, ![X]: (train(X) => ~losetime(X))).

% (2) if you go somewhere by car and meet a traffic jam, you will lose time.
% ∀x (car(x) ∧ trafficjam(x) → losetime(x))
fof(premise_2, axiom, ![X]: (car(X) & trafficjam(X) => losetime(X))).

% (3) if you lose time, you will be late for work.
% ∀x (losetime(x) → late(x))
fof(premise_3, axiom, ![X]: (losetime(X) => late(X))).

% (4) mary can get from new haven to new york city either by train or car.
% train(mary) ⊕ car(mary)
fof(premise_4, axiom, ((~(train(mary)) & (car(mary))) | ((train(mary)) & ~(car(mary))))).

% (5) mary is late for work.
% late(mary)
fof(premise_5, axiom, late(mary)).

% (6) mary gets from new haven to new york city by car. Label: True; Vampire_Check: Unknown
% car(mary)
fof(conclusion_p_infer_c, conjecture, car(mary)).
