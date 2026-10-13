# AI/ML Track Decisions

1. **Schema & Relationships (`catalogue`, `orders`, `ml`, `assistant`)**:
   - `Product` (sku PK, `catalogue/models.py:3-14`): Base catalogue item.
   - `Inventory` (OneToOne to Product, `on_delete=CASCADE` in `catalogue/models.py:17`): If a product is deleted, its inventory record is also removed, avoiding orphaned stock records. Quantity constraint `quantity__gte=0` enforces no negative inventory (`catalogue/models.py:22`).
   - `Dealer` (id PK, `dealer_code` unique, `dealers/models.py:3-13`): Verified dealers purchasing parts.
   - `Order` (`dealer` FK, `on_delete=PROTECT` in `orders/models.py:15`): Deleting a dealer is blocked if they have existing orders, preserving audit and accounting history.
   - `OrderItem` (`order` FK, `on_delete=CASCADE` in `orders/models.py:24`, `product` FK, `on_delete=PROTECT` in `orders/models.py:25`): Deleting an order cascades to its line items. Deleting a product is blocked if it appears in an order.
   - `DailySequence` (`orders/models.py:38-40`): Tracks daily sequential counters for order numbering (`ORD-YYYYMMDD-XXXX`).
   - `IdempotencyRecord` (`orders/models.py:42-46`): Maps idempotency keys (`key` PK) to request SHA-256 hashes and created orders.
   - `ChatSession` (`dealer` FK, `on_delete=SET_NULL` in `assistant/models.py:7`): If a dealer is removed, chat history is preserved for analytics while clearing the dealer foreign key.
   - `ChatMessage` (`session` FK, `on_delete=CASCADE` in `assistant/models.py:10`): Messages belong to a chat session and cascade on session deletion.

2. **Retrieval**:
   - We use a hybrid approach in `search_parts` (`assistant/services.py:18-54`). First, exact relational filtering on category and vehicle compatibility is performed via Django ORM with `icontains` for vehicle aliases (`assistant/services.py:19-24`). Next, we apply TF-IDF and Cosine Similarity on `name + brand + description` (`assistant/services.py:32-38`).
   - **Why TF-IDF (vs. Embeddings)**: The implementation uses `sklearn.feature_extraction.text.TfidfVectorizer` and `cosine_similarity` (`assistant/services.py:8-9, 33-37`) rather than dense neural embeddings. TF-IDF is lightweight, executes entirely in-memory with sub-millisecond latency, has no external API dependencies or GPU requirements, and performs reliably on exact part numbers, technical specifications, and brand keywords.
   - **Where it fails**: TF-IDF cannot handle semantic synonyms (e.g., "tyre" vs "tire", "break" vs "brake", "headlamp" vs "headlight") because it treats terms as orthogonal tokens without semantic vector embeddings.

3. **Tool-calling Loop**:
   - Implemented in `assistant/services.py:226-335`.
   - The user message is saved to the DB (`ChatMessage.objects.create` at `assistant/services.py:128`) and the entire conversation history is loaded from DB messages (`session.messages.order_by('created_at')` at `assistant/services.py:131, 147-152`) into `current_contents = list(history)` (`assistant/services.py:212`), not appended again.
   - A bounded loop executes up to 5 iterations (`for _ in range(5):`, `assistant/services.py:226`).
   - An overall 45-second deadline (`CHAT_DEADLINE_SECONDS = 45` at `assistant/services.py:222`) caps the entire request. The loop and retries stop once `time.monotonic() > deadline` (`assistant/services.py:227`), falling through to a graceful HTTP 200 fallback reply.
   - Calls `generate_with_retry` (`assistant/services.py:75-113`) setting the per-call Gemini timeout to `min(25s, time remaining until deadline)` in `config.http_options` (`assistant/services.py:93-95`) so one request can never exceed 60 seconds. The retry helper also checks the deadline before each attempt (`assistant/services.py:82`).
   - If the model returns `function_calls` (`assistant/services.py:240`), we append the model call to contents, execute each tool locally (`search_parts` line 261, `check_stock` line 272, `create_draft_order` line 279), record tool call history, and append `types.Part.from_function_response` to `current_contents` (`assistant/services.py:324-329`).
   - The loop continues until the model emits a text `reply` (`assistant/services.py:330-332`) or terminates, followed by post-check sanitization.
   - On any unhandled exception, the `except` block (`assistant/services.py:336-339`) returns a polite fallback message (HTTP 200), not a 500 error.

4. **Live Stock and Prices**:
   - The system prompt explicitly instructs the assistant (`assistant/services.py:140`): "ALWAYS fetch live stock and price using check_stock or search_parts before quoting them. Do NOT rely on memory from previous turns."
   - The `check_stock` function (`assistant/services.py:56-64`) queries `Product` and `Inventory` directly from the live PostgreSQL database at invocation time.

5. **Prompt Injection & Untrusted Data**:
   - In `search_parts` (`assistant/services.py:51`), untrusted descriptions are delimited: `===UNTRUSTED_DATA_START==={p.description}===UNTRUSTED_DATA_END===`.
   - System prompt instructions (`assistant/services.py:142`) instruct the model that descriptions contain untrusted data and forbid following enclosed instructions or repeating unofficial discount codes.
   - Safe post-check sanitization (`assistant/services.py:344-372`): Prices quoted in the final reply are normalized (stripping commas and currency symbols) and verified against `valid_numbers` collected from tool outputs (`assistant/services.py:347-356`). Order numbers matching `ORD-YYYYMMDD-NNNN` are strictly preserved (`assistant/services.py:345, 364-372`). Any unverified price is redacted to `[REDACTED]`. SKU redaction now keeps any SKU that exists in the database (`assistant/services.py:358-362`), so price verification is the main grounding guard.
   - `cited_skus` are built ONLY from SKUs that appear in the final reply text (after redaction) AND exist in the database (`assistant/services.py:374-380`). SKUs from tool-call arguments alone are excluded.
   - **Where it fails**: Elaborate indirect injection, foreign-language obfuscation, or model hallucination that disregards system delimiters could theoretically bypass prompt-level guards, though the regex post-check acts as a deterministic second line of defense.

6. **Forecasting Approach & Validation**:
   - Implemented in `ml/forecast_script.py`. We use a Ridge regression model regularized with `alpha=10.0` (`ml/forecast_script.py:34`), engineered with a fixed trend origin (`ml/forecast_script.py:31`), ISO week-of-year, Diwali proximity (`weeks_to_diwali`, `weeks_since_diwali` at `ml/forecast_script.py:77-89`), promo flags, and one-hot category + SKU dummies (`ml/forecast_script.py:162-173`).
   - **SWLY-Scaled**: Same-week-last-year is scaled by the ratio of recent 4-week sales level to last year's recent level (`_compute_swly_scaled` at `ml/forecast_script.py:99-133`), so it adapts to growth/decline rather than copying last year's volume verbatim. The scale ratio is capped between 0.2× and 5.0× to avoid blowups.
   - **Validation**: Evaluated using rolling-origin time-series cross-validation across 6 folds (including pre-Diwali `2025-09-22` and post-Diwali `2025-10-20` windows) over a 3-way grid of blend weights (Avg, SWLY-scaled, Ridge; each 0.0–0.6 in steps of 0.1, summing to 1.0) (`ml/forecast_script.py:186-250`). Optimal blend selected: **Avg=10%, SWLY=10%, Ridge=80%** (mean WAPE: **0.2839**). The previous 2-way blend (Avg=20%, Ridge=80%) scored 0.2843, while adding SWLY-scaled yields 0.2839 (essentially neutral). Furthermore, note that scaled SWLY is worse than raw (unscaled) SWLY on most folds, because scaling by recent 4-week moving average ratios amplifies short-term noise on seasonal items.
   - **Backtest Table (WAPE Metrics across 6 folds)**:
     | Cutoff Date | Last Value | Recent Avg (4w) | SWLY-Scaled | Ridge | Blend (10% Avg / 10% SWLY / 80% Ridge) |
     | :--- | :--- | :--- | :--- | :--- | :--- |
     | 2025-09-22 | 0.3849 | 0.4323 | **0.3204 (Best)** | 0.4532 | 0.4182 |
     | 2025-10-20 | 1.2628 | 0.8487 | 0.7715 | 0.2553 | **0.2463 (Best)** |
     | 2026-06-01 | 0.4280 | 0.2978 | 0.4309 | 0.2536 | **0.2486 (Best)** |
     | 2026-06-29 | 0.3198 | 0.2862 | 0.3459 | 0.2379 | **0.2264 (Best)** |
     | 2026-07-27 | 0.3350 | 0.2752 | 0.3639 | 0.2839 | **0.2378 (Best)** |
     | 2026-08-24 | 0.3441 | **0.2571 (Best)** | 0.4350 | 0.3828 | 0.3259 |
   - **Honest Performance & Competition Note**:
     - On fold `2026-08-24`, the recent 4-week average beats the blend (**0.2571** vs 0.3259), as recent steady sales were better captured by moving average than the linear trend.
     - On fold `2025-09-22` (pre-Diwali surge), SWLY-scaled is the strongest baseline (**0.3204**) because seasonal patterns repeat year-over-year, and the blend (0.4182) cannot fully capture the holiday spike with only 10% SWLY weight. A per-fold adaptive ensemble could further improve this.
     - During sudden holiday regime changes—notably the immediate post-Diwali crash on `2025-10-20`—the 4-week average fails badly (**0.8487** WAPE) because backward-looking moving averages lag behind the collapse, whereas Ridge features (`weeks_since_diwali`) correctly anticipate the slump, allowing the Blend to achieve **0.2463** WAPE. Across all 6 folds, the 3-way 10%/10%/80% blend delivers the best overall cross-validation score (**0.2839**).
   - **Leakage Prevention**: Strictly filtered on each fold: `train = sales[sales['week_start'] <= cutoff]` (`ml/forecast_script.py:202, 261`).

7. **Handling Idempotency (Orders)**:
   - Order creation guarantees unique, monotonically increasing order numbers (`ORD-YYYYMMDD-XXXX`) via `DailySequence` in `orders/models.py:38-40`. Sequential ordering concurrency is handled by locking via `DailySequence.objects.select_for_update().get(date=today)` within a database transaction (`orders/services.py:47-49`).
   - The API supports idempotency via the `Idempotency-Key` HTTP request header (`orders/views.py:50`).
   - In `orders/services.py:80-101`, idempotency races are handled by database uniqueness on `IdempotencyRecord.key` (`orders/models.py:43`, primary key) resolved via `IdempotencyRecord.objects.get_or_create(key=idempotency_key, defaults={'request_hash': request_hash})` at `orders/services.py:81-84`.
   - If an existing key is presented:
     - Matching request hash returns the previously created order (HTTP 201 replay) without duplicating side effects (`orders/services.py:93-94`).
     - Mismatched request hash raises `IDEMPOTENCY_CONFLICT` (HTTP 409) (`orders/services.py:86-91`).
     - Concurrent request still being processed raises `IDEMPOTENCY_CONFLICT` (HTTP 409) (`orders/services.py:96-100`).

8. **Handling Edge Cases in Forecast**:
   - **Promotions & Diwali**: Engineered `promo_flag` along with bilateral distance features `weeks_to_diwali` and `weeks_since_diwali` (`ml/forecast_script.py:77-89, 162-163`).
   - **Rare / Intermittent SKUs**: SKUs with zero-sales in > 50% of history weeks (3 SKUs: `BRK-1088`, `ELE-1006`, `GRP-1043`) are forecasted using Croston's method with Syntetos-Boylan Approximation (SBA) (`ml/forecast_script.py:46-66, 150-156, 354-358`).
   - **New SKUs (Zero History)**: New SKUs borrow category-level averages (`cat_avg`) rather than arbitrary defaults (`ml/forecast_script.py:159, 360-368`).
   - **Worst SKUs**: Intermittent low-volume parts with sporadic lumpiness remain the most challenging for linear regression due to mean reversion.

9. **Weakest Part & Next Steps**:
   - **Weakest**: Retrieval relies on lexical TF-IDF which cannot resolve semantic synonyms or colloquial phrasing; linear Ridge regression cannot model complex non-linear feature interactions.
   - **With two more days**:
     1. Migrate catalogue search to dense semantic embeddings with pgvector / HNSW indexing using a multilingual embedding model.
     2. Implement gradient-boosted trees (LightGBM) with Croston's intermittent demand forecasting method for sparse SKUs.
