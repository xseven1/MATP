% (1) a unix operating system used in the lab computers is a piece of software.
% ∀x (unixos(x) ∧ usedinlab(x) → software(x))
fof(premise_1, axiom, ![X]: (unixos(X) & usedinlab(X) => software(X))).

% (2) all versions of macos used in the lab computer are based on unix operating systems.
% ∀x (macos(x) ∧ usedinlab(x) → unixos(x))
fof(premise_2, axiom, ![X]: (macos(X) & usedinlab(X) => unixos(X))).

% (3) a lab computer uses either macos or linux.
% ∀x (usedinlab(x) → (macos(x) ⊕ linux(x)))
fof(premise_3, axiom, ![X]: (usedinlab(X) => (((~(macos(X)) & (linux(X))) | ((macos(X)) & ~(linux(X))))))).

% (4) all linux computers in the lab are convenient.
% ∀x (linux(x) ∧ usedinlab(x) → convenient(x))
fof(premise_4, axiom, ![X]: (linux(X) & usedinlab(X) => convenient(X))).

% (5) all software used in the lab computers is written with code. Label 
% ∀x (software(x) ∧ usedinlab(x) → writtenwithcode(x))
fof(premise_5, axiom, ![X]: (software(X) & usedinlab(X) => writtenwithcode(X))).

% (6) if something is convenient in the lab computer, then it is popular.
% ∀x (convenient(x) ∧ usedinlab(x) → popular(x))
fof(premise_6, axiom, ![X]: (convenient(X) & usedinlab(X) => popular(X))).

% (7) burger is used in the lab computer, and it is written with code and a new version of macos.
% usedinlab(burger) ∧ writtenwithcode(burger) ∧ macos(burger)
fof(premise_7, axiom, usedinlab(burger) & writtenwithcode(burger) & macos(burger)).

% (8) pytorch is used in the lab computer, and pytorch is neither a linux system nor a piece of software.
% usedinlab(pytorch) ∧ ¬(linux(pytorch) ∨ software(pytorch))
fof(premise_8, axiom, usedinlab(pytorch) & ~(linux(pytorch) | software(pytorch))).

% (9) PyTorch is not popular and it is not written with code. Label: False; Vampire_Check: Error(Contradiction exists in Premises)
% ¬popular(pytorch) ∧ ¬writtenwithcode(pytorch)
fof(conclusion_p_infer_c, conjecture, ~popular(pytorch) & ~writtenwithcode(pytorch)).
