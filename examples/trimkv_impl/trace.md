# Agent Trace Log — TrimKV implementation

---

STEP: 1

GOAL:
Gather source material: the paper's exact algorithm + hyperparameters, and the reference repo's file structure.

FILES READ:
- WebFetch arXiv:2512.03324v2
- WebFetch github.com/ngocbh/trimkv

TOOLS USED:
- WebFetch (x2)

DECISION:
Base implementation on: (a) retention gate MLP hidden=512, bias=18.0; (b) current score beta_i^(t-i); (c) argmin eviction when |cache|>M; (d) attention logits += (t-i)*log beta; (e) capacity loss mean_t max(0, sum_i beta_i^(t-i) - M)/t with lambda=1.0. Target Qwen3 to match upstream repo; keep wrapping mechanical enough to port to other HF decoders.

RESULT:
Clear paper→code mapping.

NEXT PLAN:
Mirror the existing harness session schema and scaffold the project.

---

STEP: 2

GOAL:
Decide harness log format and set up the project directory tree.

FILES READ:
- D:/N Projects/Harness-Benchmark-Skill/examples/auto_eda/session_meta.json
- .../tool_calls.json
- .../trace.md
- .../diff_summary.md

TOOLS USED:
- Bash (ls, mkdir)
- Read (x4)

DECISION:
Create D:/N projects/KV-Cache-memory-bound/{trimkv/models,train,examples} and a sibling harness session at D:/N Projects/Harness-Benchmark-Skill/examples/trimkv_impl so mcp__harness__* tools surface this session alongside auto_eda.

RESULT:
Folders created. Harness schema reproduced.

NEXT PLAN:
Write the retention gate.

---

STEP: 3

GOAL:
Implement RetentionGate.

FILES MODIFIED:
- trimkv/retention_gate.py (new)

TOOLS USED:
- Write

DECISION:
Linear(d, 512) -> GELU -> Linear(512, H_kv). Last layer bias init 18.0, weights zero-init so all heads start equal and near-1. Clamp logits to [-30, 30] before sigmoid for stability given the large init.

RESULT:
Deterministic near-1 beta at init; gate learns to drive specific tokens toward 0.

---

STEP: 4

GOAL:
Implement TrimKVCache with exponential-decay argmin eviction.

FILES MODIFIED:
- trimkv/cache_utils.py (new)

DECISION:
Store log_beta and creation_step per token. Current log score at step t = log_beta * (t - creation_step). Eviction keeps top-M tokens by per-head amin aggregation (GQA-safe, preserves temporal order via sort after gather). buffer_size allows amortised eviction.

NEXT PLAN:
Attention kernel.

---

STEP: 5

GOAL:
Retention-weighted attention kernel.

FILES MODIFIED:
- trimkv/attention.py (new)

DECISION:
logits = (q k^T)/sqrt(d) + log_scores.unsqueeze(-2); softmax in fp32. Broadcast log_scores across T_q and across grouped query heads via repeat_interleave. Additive bias keeps the kernel FA-compatible in principle.

---

STEP: 6

GOAL:
Training objectives.

FILES MODIFIED:
- trimkv/losses.py (new)

DECISION:
distillation_loss = T^2 * KL(student||teacher) + ce_weight * CE (labels optional). capacity_loss constructs the full (T, T) age matrix once, exponentiates once (log_beta * age), applies causal mask, sums over i, overflow = relu(sum - M), divides by (t+1), averages over heads+layers. O(T^2*H*B) per layer — acceptable for training-time sequences.

---

STEP: 7

GOAL:
Patch Qwen3 attention to use the gate + TrimKVCache.

FILES MODIFIED:
- trimkv/models/qwen3.py (new)

DECISION:
Monkey-patch self_attn.forward per layer via closure over layer_idx. Honour the stock q_norm/k_norm + RoPE (apply_rotary_pos_emb from transformers.models.qwen3.modeling_qwen3). TrimKVQwen3ForCausalLM exposes new_cache(), generate(), and gate_parameters() so the trainer only updates gates.

LIMITATION:
TrimKVCache is not a subclass of transformers Cache; HF's own generate() will not use it. Our simple generate loop calls base(input_ids=last, past_key_values=cache) each step, which is what the reference repo does.

---

STEP: 8

GOAL:
Training script + inference example + README.

FILES MODIFIED:
- train/train.py (new)
- examples/test_qwen3.py (new)
- README.md (new)

DECISION:
Train only gates; teacher = unwrapped HF model, student = frozen base + trainable gates. Use output_hidden_states=True to fetch the *input* hidden state of each decoder layer and pass to that layer's gate for the capacity loss. Checkpoint gates as a dict keyed by layer_{i}.

RESULT:
End-to-end runnable. Infer with python examples/test_qwen3.py --model Qwen/Qwen3-1.7B --memory-size 256. Train with python train/train.py --dataset-path data.jsonl.

---

STEP: 9

GOAL:
Persist this session to harness.

FILES MODIFIED:
- Harness-Benchmark-Skill/examples/trimkv_impl/session_meta.json
- .../tool_calls.json
- .../trace.md
- .../diff_summary.md

RESULT:
mcp__harness__refresh will pick this up as session id "trimkv_impl". Use mcp__harness__get_session, get_trace, get_tool_calls, get_diffs to inspect.
