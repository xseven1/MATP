% (1) if you go somewhere by train, you will not lose time.
% ∀x (train(x) → ¬losetime(x))
fof(premise_1, axiom, ![X]: (train(X) => ~losetime(X))).

% (2) if you go somewhere by car and meet a traffic jam, you will lose time.
% ∀x (car(x) ∧ trafficjam(x) → losetime(x))
fof(premise_2, axiom, ![X]: (car(X) & trafficjam(X) => losetime(X))).

% (3) if you lose time, you will be late for work.
% ∀x (losetime(x) → lateforwork(x))
fof(premise_3, axiom, ![X]: (losetime(X) => lateforwork(X))).

% (4) mary can get from new haven to new york city either by train or car.
% train(mary) ⊕ car(mary)
fof(premise_4, axiom, ((~(train(mary)) & (car(mary))) | ((train(mary)) & ~(car(mary))))).

% (5) mary is late for work.
% lateforwork(mary)
fof(premise_5, axiom, lateforwork(mary)).

% (6) mary gets from new haven to new york city by train. Label: False; Vampire_Check: Unknown
% train(mary)
fof(conclusion_p_infer_c, conjecture, train(mary)).
