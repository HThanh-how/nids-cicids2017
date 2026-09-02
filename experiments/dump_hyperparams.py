"""Dump the full hyperparameter grid to JSON so the paper's table is generated
from the same objects the experiments instantiate (reviewer 1, concern 5)."""
import json
import os

import run_v3 as exp

os.makedirs(exp.OUT_DIR, exist_ok=True)
out = {name: {k: (v if isinstance(v, (int, float, str, bool, type(None)))
                  else str(v))
              for k, v in clf.get_params().items()}
       for name, clf in exp.build_models(42).items()}
out["_note"] = ("random_state is set to the split seed at construction time; "
                "the value shown is the seed used for this dump (42).")
with open(os.path.join(exp.OUT_DIR, "S8b_hyperparameters.json"), "w",
          encoding="utf-8") as fh:
    json.dump(out, fh, indent=2, default=str)
print(json.dumps({k: len(v) for k, v in out.items() if isinstance(v, dict)},
                 indent=2))
