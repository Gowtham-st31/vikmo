#!/usr/bin/env python3
"""
verify_citations.py - Extracts every file:line and file:start-end citation in DECISIONS.md,
fetches the corresponding lines from the actual codebase, validates whether the snippet
matches the claim immediately preceding/surrounding it, and reports any discrepancies.
"""

import re
import os
import sys

# Set console encoding to UTF-8
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DECISIONS_FILE = os.path.join(BASE_DIR, "DECISIONS.md")

CITATION_REGEX = re.compile(
    r'`([a-zA-Z0-9_\/]+\.py):([0-9]+(?:-[0-9]+)?(?:,\s*[0-9]+(?:-[0-9]+)?)*)`'
)

def get_lines(filepath, line_spec):
    """Parses line spec like '128' or '77-89' or '8-9, 33-37' and returns {line_no: line_content}."""
    full_path = os.path.join(BASE_DIR, filepath)
    if not os.path.exists(full_path):
        return None, f"File not found: {full_path}"
    
    with open(full_path, "r", encoding="utf-8") as f:
        file_lines = f.readlines()
        
    results = {}
    parts = [p.strip() for p in line_spec.split(",")]
    for p in parts:
        if "-" in p:
            start, end = map(int, p.split("-"))
            for l_num in range(start, end + 1):
                if 1 <= l_num <= len(file_lines):
                    results[l_num] = file_lines[l_num - 1].rstrip()
                else:
                    results[l_num] = f"<OUT OF BOUNDS: line {l_num}>"
        else:
            l_num = int(p)
            if 1 <= l_num <= len(file_lines):
                results[l_num] = file_lines[l_num - 1].rstrip()
            else:
                results[l_num] = f"<OUT OF BOUNDS: line {l_num}>"
    return results, None


def verify():
    with open(DECISIONS_FILE, "r", encoding="utf-8") as f:
        decisions_lines = f.readlines()

    total_citations = 0
    mismatches = 0

    print("=" * 80)
    print("VERIFYING DECISIONS.md CITATIONS")
    print("=" * 80)

    for i, line in enumerate(decisions_lines, 1):
        for m in CITATION_REGEX.finditer(line):
            filepath = m.group(1)
            line_spec = m.group(2)
            
            # The descriptor immediately preceding the citation
            pre_context = line[max(0, m.start() - 70):m.start()].strip()
            total_citations += 1
            
            lines_dict, err = get_lines(filepath, line_spec)
            if err:
                print(f"[MISMATCH] DECISIONS.md Line {i}: `{filepath}:{line_spec}` -> {err}")
                mismatches += 1
                continue
            
            snippet = "\n    ".join(f"{l_num}: {text}" for l_num, text in lines_dict.items())
            all_text = " ".join(lines_dict.values())
            
            is_valid = True
            reasons = []

            # 1. Out of file bounds
            if any("<OUT OF BOUNDS" in line_val for line_val in lines_dict.values()):
                is_valid = False
                reasons.append("Line number out of file bounds")

            # 2. Match claims based on preceding descriptor
            if "Product (sku PK" in pre_context:
                if "class Product" not in all_text or "sku = models.CharField" not in all_text:
                    is_valid = False
                    reasons.append("Expected Product model definition with sku PK")
            elif "Inventory (OneToOne" in pre_context or ("CASCADE" in pre_context and filepath == "catalogue/models.py"):
                if "models.OneToOneField" not in all_text or "CASCADE" not in all_text:
                    is_valid = False
                    reasons.append("Expected Inventory OneToOneField with on_delete=CASCADE")
            elif "quantity__gte=0" in pre_context:
                if "quantity__gte=0" not in all_text:
                    is_valid = False
                    reasons.append("Expected quantity__gte=0 constraint")
            elif "Dealer (id PK" in pre_context:
                if "class Dealer" not in all_text or "dealer_code = models.CharField" not in all_text:
                    is_valid = False
                    reasons.append("Expected Dealer model with dealer_code unique")
            elif "Order (`dealer` FK" in pre_context or ("on_delete=PROTECT" in pre_context and "dealer" in pre_context):
                if "dealer = models.ForeignKey(Dealer, on_delete=models.PROTECT" not in all_text:
                    is_valid = False
                    reasons.append("Expected Order dealer FK with on_delete=PROTECT")
            elif "OrderItem (`order` FK" in pre_context or ("on_delete=CASCADE" in pre_context and filepath == "orders/models.py"):
                if "order = models.ForeignKey" not in all_text or "CASCADE" not in all_text:
                    is_valid = False
                    reasons.append("Expected OrderItem order FK with on_delete=CASCADE")
            elif "`product` FK" in pre_context and filepath == "orders/models.py":
                if "product = models.ForeignKey" not in all_text or "PROTECT" not in all_text:
                    is_valid = False
                    reasons.append("Expected OrderItem product FK with on_delete=PROTECT")
            elif "DailySequence" in pre_context and filepath == "orders/models.py":
                if "class DailySequence" not in all_text:
                    is_valid = False
                    reasons.append("Expected DailySequence model")
            elif "IdempotencyRecord" in pre_context and filepath == "orders/models.py" and "key" not in pre_context:
                if "class IdempotencyRecord" not in all_text:
                    is_valid = False
                    reasons.append("Expected IdempotencyRecord model")
            elif "ChatSession (`dealer` FK" in pre_context:
                if "class ChatSession" not in all_text or "SET_NULL" not in all_text:
                    is_valid = False
                    reasons.append("Expected ChatSession dealer FK with SET_NULL")
            elif "ChatMessage (`session` FK" in pre_context:
                if "class ChatMessage" not in all_text or "CASCADE" not in all_text:
                    is_valid = False
                    reasons.append("Expected ChatMessage session FK with CASCADE")

            # assistant/services.py
            elif "search_parts" in pre_context and "assistant/services.py:18-54" in f"{filepath}:{line_spec}":
                if "def search_parts" not in all_text:
                    is_valid = False
                    reasons.append("Expected search_parts function definition")
            elif "icontains" in pre_context or "vehicle aliases" in pre_context:
                if "icontains" not in all_text or "category" not in all_text:
                    is_valid = False
                    reasons.append("Expected category and vehicle fitment filtering")
            elif "TF-IDF and Cosine Similarity" in pre_context:
                if "TfidfVectorizer" not in all_text or "cosine_similarity" not in all_text:
                    is_valid = False
                    reasons.append("Expected TF-IDF vectorizer and cosine_similarity")
            elif "TfidfVectorizer` and `cosine_similarity`" in pre_context:
                if "TfidfVectorizer" not in all_text and "cosine_similarity" not in all_text:
                    is_valid = False
                    reasons.append("Expected TfidfVectorizer and cosine_similarity imports/usage")
            elif "Tool-calling Loop" in line and "226-335" in line_spec:
                if "for _ in range(5):" not in all_text:
                    is_valid = False
                    reasons.append("Expected tool calling loop implementation")
            elif "ChatMessage.objects.create" in pre_context and "user" in line:
                if "ChatMessage.objects.create" not in all_text or "role=\"user\"" not in all_text:
                    is_valid = False
                    reasons.append("Expected user ChatMessage.objects.create")
            elif "session.messages.order_by('created_at')" in pre_context:
                if "messages.order_by" not in all_text:
                    is_valid = False
                    reasons.append("Expected session.messages.order_by history loading")
            elif "current_contents = list(history)" in pre_context:
                if "current_contents = list(history)" not in all_text:
                    is_valid = False
                    reasons.append("Expected 'current_contents = list(history)'")
            elif "for _ in range(5):" in pre_context:
                if "for _ in range(5):" not in all_text:
                    is_valid = False
                    reasons.append("Expected bounded loop 'for _ in range(5):'")
            elif "CHAT_DEADLINE_SECONDS = 45" in pre_context:
                if "CHAT_DEADLINE_SECONDS = 45" not in all_text:
                    is_valid = False
                    reasons.append("Expected CHAT_DEADLINE_SECONDS = 45")
            elif "time.monotonic() > deadline" in pre_context:
                if "time.monotonic() > deadline" not in all_text:
                    is_valid = False
                    reasons.append("Expected loop deadline check")
            elif "generate_with_retry" in pre_context and "75-113" in line_spec:
                if "def generate_with_retry" not in all_text:
                    is_valid = False
                    reasons.append("Expected generate_with_retry function")
            elif "config.http_options" in pre_context:
                if "http_options" not in all_text or "timeout" not in all_text:
                    is_valid = False
                    reasons.append("Expected per-call timeout in config.http_options")
            elif "deadline before each attempt" in pre_context:
                if "now >= deadline" not in all_text and "deadline is not None" not in all_text:
                    is_valid = False
                    reasons.append("Expected deadline check before retry ('now >= deadline')")
            elif "function_calls" in pre_context:
                if "response.function_calls" not in all_text:
                    is_valid = False
                    reasons.append("Expected response.function_calls")
            elif "from_function_response" in pre_context:
                if "from_function_response" not in all_text:
                    is_valid = False
                    reasons.append("Expected Part.from_function_response")
            elif "reply" in pre_context and "330-332" in line_spec:
                if "response.text" not in all_text:
                    is_valid = False
                    reasons.append("Expected text reply handling")
            elif "except" in pre_context and "336-339" in line_spec:
                if "except Exception" not in all_text:
                    is_valid = False
                    reasons.append("Expected exception fallback handler")
            elif "instructs the assistant" in pre_context and "140" in line_spec:
                if "ALWAYS fetch live stock" not in all_text:
                    is_valid = False
                    reasons.append("Expected 'ALWAYS fetch live stock' prompt instruction")
            elif "check_stock` function" in pre_context:
                if "def check_stock" not in all_text:
                    is_valid = False
                    reasons.append("Expected check_stock function definition")
            elif "search_parts" in pre_context and "untrusted" in line:
                if "UNTRUSTED_DATA_START" not in all_text:
                    is_valid = False
                    reasons.append("Expected UNTRUSTED_DATA_START delimiter")
            elif "System prompt instructions" in pre_context and "142" in line_spec:
                if "UNTRUSTED DATA" not in all_text:
                    is_valid = False
                    reasons.append("Expected UNTRUSTED DATA system prompt guideline")
            elif "post-check sanitization" in pre_context and "344-372" in line_spec:
                if "ORDER_NUM_RE" not in all_text or "redact_price_number" not in all_text:
                    is_valid = False
                    reasons.append("Expected safe post-check sanitization block")
            elif "valid_numbers" in pre_context:
                if "valid_numbers" not in all_text:
                    is_valid = False
                    reasons.append("Expected valid_numbers verification")
            elif "ORD-YYYYMMDD-NNNN" in pre_context:
                if "ORDER_NUM_RE" not in all_text:
                    is_valid = False
                    reasons.append("Expected ORDER_NUM_RE order number preservation")
            elif "database" in pre_context and "358-362" in line_spec:
                if "redact_sku" not in all_text or "Product.objects.filter" not in all_text:
                    is_valid = False
                    reasons.append("Expected SKU DB existence check in redaction")
            elif "cited_skus" in line and "374-380" in line_spec:
                if "cited_skus" not in all_text or "Product.objects.filter" not in all_text:
                    is_valid = False
                    reasons.append("Expected cited_skus DB existence validation")

            # ml/forecast_script.py
            elif "alpha=10.0" in pre_context:
                if "RIDGE_ALPHA = 10.0" not in all_text:
                    is_valid = False
                    reasons.append("Expected RIDGE_ALPHA = 10.0")
            elif "trend origin" in pre_context:
                if "TREND_ORIGIN" not in all_text:
                    is_valid = False
                    reasons.append("Expected TREND_ORIGIN definition")
            elif "weeks_to_diwali" in pre_context and filepath == "ml/forecast_script.py":
                if "weeks_to_diwali" not in all_text:
                    is_valid = False
                    reasons.append("Expected weeks_to_diwali feature")
            elif "dummies" in pre_context:
                if "get_dummies" not in all_text or "feature_base" not in all_text:
                    is_valid = False
                    reasons.append("Expected feature list and one-hot dummies")
            elif "_compute_swly_scaled" in pre_context:
                if "def _compute_swly_scaled" not in all_text:
                    is_valid = False
                    reasons.append("Expected def _compute_swly_scaled")
            elif "grid of blend weights" in pre_context:
                if "blend_wapes" not in all_text and "for avg_w in weight_range:" not in all_text:
                    is_valid = False
                    reasons.append("Expected grid search loop over blend weights")
            elif "Leakage Prevention" in line or "train = sales[sales['week_start'] <= cutoff]" in pre_context:
                if "cutoff" not in all_text or "train" not in all_text:
                    is_valid = False
                    reasons.append("Expected train cutoff filter preventing leakage")
            elif "Croston" in pre_context and filepath == "ml/forecast_script.py":
                if "croston_sba" not in all_text:
                    is_valid = False
                    reasons.append("Expected croston_sba implementation")
            elif "cat_avg" in pre_context or "category-level averages" in pre_context:
                if "cat_avg" not in all_text:
                    is_valid = False
                    reasons.append("Expected category average for new SKUs")

            # orders/services.py & orders/views.py
            elif "select_for_update" in pre_context:
                if "select_for_update" not in all_text:
                    is_valid = False
                    reasons.append("Expected select_for_update sequence lock")
            elif "Idempotency-Key" in pre_context:
                if "Idempotency-Key" not in all_text:
                    is_valid = False
                    reasons.append("Expected Idempotency-Key header lookup")
            elif "idempotency races are handled" in pre_context:
                if "IdempotencyRecord" not in all_text:
                    is_valid = False
                    reasons.append("Expected IdempotencyRecord handling")
            elif "IdempotencyRecord.key" in pre_context:
                if "key = models.CharField" not in all_text:
                    is_valid = False
                    reasons.append("Expected IdempotencyRecord.key PK")
            elif "get_or_create" in pre_context and filepath == "orders/services.py":
                if "get_or_create" not in all_text:
                    is_valid = False
                    reasons.append("Expected IdempotencyRecord get_or_create")
            elif "previously created order" in pre_context:
                if "record.order" not in all_text:
                    is_valid = False
                    reasons.append("Expected order replay on matching hash")
            elif "Mismatched request hash" in pre_context:
                if "IDEMPOTENCY_CONFLICT" not in all_text:
                    is_valid = False
                    reasons.append("Expected IDEMPOTENCY_CONFLICT on mismatched hash")
            elif "Concurrent request" in pre_context:
                if "IDEMPOTENCY_CONFLICT" not in all_text:
                    is_valid = False
                    reasons.append("Expected IDEMPOTENCY_CONFLICT on concurrent request")

            status = "MATCH" if is_valid else "MISMATCH"
            if not is_valid:
                mismatches += 1
                
            print(f"[{status}] DECISIONS.md Line {i}: `{filepath}:{line_spec}`")
            print(f"    Claim context: ...{pre_context}`{filepath}:{line_spec}`")
            print(f"    Cited Code:\n    {snippet}")
            if not is_valid:
                print(f"    --> Flagged issue: {', '.join(reasons)}")
            print("-" * 80)

    print(f"\nVerification Complete: {total_citations} citations checked.")
    if mismatches == 0:
        print("[SUCCESS] Zero mismatches found! All citations precisely match current codebase.")
    else:
        print(f"[WARNING] {mismatches} citation mismatches found! Please correct stale lines.")
    print("=" * 80)
    return mismatches

if __name__ == "__main__":
    sys.exit(verify())
