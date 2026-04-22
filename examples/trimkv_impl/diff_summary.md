# Diff Summary Log — TrimKV implementation

---

STEP: 4
FILES CHANGED: requirements.txt, setup.py, trimkv/__init__.py, trimkv/models/__init__.py
LINES ADDED: 40
LINES REMOVED: 0
REASON FOR CHANGE: Project scaffolding — installable `trimkv` package + deps (torch>=2.3, transformers>=4.45, accelerate, einops).

---

STEP: 5
FILES CHANGED: trimkv/retention_gate.py
LINES ADDED: 42
LINES REMOVED: 0
REASON FOR CHANGE: RetentionGate MLP (512 hidden, GELU) emitting per-head beta; bias init 18.0 so sigmoid≈1 at start (paper §3, Algorithm 1). Last layer weight zero-init and logit clamp [-30, 30] for numerical stability with the large init.

---

STEP: 6
FILES CHANGED: trimkv/cache_utils.py
LINES ADDED: 145
LINES REMOVED: 0
REASON FOR CHANGE: Memory-bounded KV cache. Stores keys/values/log_beta/creation_step per layer. current_log_scores(t) returns (t - creation_step) * log_beta. _enforce_budget aggregates per-head log scores with amin across heads, selects top-M via topk+sort, gathers. Supports `buffer_size` to amortise eviction.

---

STEP: 7
FILES CHANGED: trimkv/attention.py
LINES ADDED: 56
LINES REMOVED: 0
REASON FOR CHANGE: Retention-weighted attention (paper Eq. 2). logits = q·kᵀ/√d + log_scores broadcast over T_q; GQA via repeat_interleave on key/value/log_scores; softmax in fp32 cast back to value dtype. Additive-bias design stays compatible with FlashAttention-style kernels that accept attention bias.

---

STEP: 8
FILES CHANGED: trimkv/losses.py
LINES ADDED: 74
LINES REMOVED: 0
REASON FOR CHANGE: Training objectives. distillation_loss: T^2·KL(s||t) (+ optional CE on labels at ce_weight). capacity_loss: causal age matrix (T_t, T_i), log_beta·age → exp, sum_i, overflow = relu(sum - M), divide by (t+1), mean across heads + layers. Matches paper §4 with λ_cap=1.0 default.

---

STEP: 9
FILES CHANGED: trimkv/models/qwen3.py
LINES ADDED: 132
LINES REMOVED: 0
REASON FOR CHANGE: TrimKVQwen3ForCausalLM wrapping HF Qwen3. Per-layer RetentionGate installed on self_attn; forward monkey-patched with a closure over layer_idx that performs q/k/v projection, QK-norm + RoPE (delegated to upstream helpers), beta = gate(hidden), cache.update, retention_weighted_attention. new_cache() allocates a TrimKVCache sized to M (+buffer). generate() uses the cache across decode steps.

---

STEP: 10
FILES CHANGED: train/train.py
LINES ADDED: 122
LINES REMOVED: 0
REASON FOR CHANGE: Gate-only distillation trainer. Frozen teacher (plain HF model) and frozen student base; only student.gate_parameters() are trainable. Per batch: teacher forward (no grad) → teacher logits; student forward with output_hidden_states=True → student logits + per-layer input hidden states; run each gate on its layer input to collect betas; L = KL + ce_weight·CE + λ_cap·capacity_loss; AdamW(lr=1e-3), grad-clip 1.0; checkpoint to checkpoints/gates_M{M}/gates.pt.

---

STEP: 11
FILES CHANGED: examples/test_qwen3.py
LINES ADDED: 42
LINES REMOVED: 0
REASON FOR CHANGE: Inference smoke test. Loads Qwen3 via load_trimkv_qwen3, optional --gate-ckpt to restore trained gates, runs model.generate() under a memory-bounded cache.

---

STEP: 12
FILES CHANGED: README.md
LINES ADDED: 108
LINES REMOVED: 0
REASON FOR CHANGE: User-facing docs — method summary, install, quick inference, training, porting, paper→code table, harness logging pointer, known limitations.

---

STEP: 13
FILES CHANGED: Harness-Benchmark-Skill/examples/trimkv_impl/{session_meta.json, tool_calls.json, trace.md, diff_summary.md}
LINES ADDED: ~280
LINES REMOVED: 0
REASON FOR CHANGE: Session persistence — mirrors the auto_eda session schema so mcp__harness__refresh + list_sessions surfaces this run; get_trace / get_tool_calls / get_diffs return structured views.
