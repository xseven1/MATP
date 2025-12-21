% (1) rafa nadal was born in mallorca.
% borninmallorca(rafa)
fof(premise_1, axiom, borninmallorca(rafa)).

% (2) rafa nadal is a professional tennis player.
% professional(rafa) ∧ tennisplayer(rafa)
fof(premise_2, axiom, professional(rafa) & tennisplayer(rafa)).

% (3) nadal's win ratio is high.
% highwinratio(rafa)
fof(premise_3, axiom, highwinratio(rafa)).

% (4) all players in the big 3 are professionals who have a high win ratio.
% ∀x (big3(x) → (professional(x) ∧ highwinratio(x)))
fof(premise_4, axiom, ![X]: (big3(X) => (professional(X) & highwinratio(X)))).

% (4) nadal is in the big 3. Label: True; Vampire_Check: Unknown
% big3(rafa)
fof(conclusion_p_infer_c, conjecture, big3(rafa)).
