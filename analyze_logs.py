import re
import sys
from collections import Counter

log_file = "logs/polybot.log"  # Adjust path if needed, e.g. /var/log/syslog or journalctl output
# We'll use stdin for flexibility with journalctl
# usage: sudo journalctl -u polybot --no-pager | python3 analyze_logs.py

def analyze():
    llm_decisions = []
    skip_reasons = []
    errors = []
    
    # regex patterns
    llm_pattern = re.compile(r"🧠 LLM Decision: (\w+) \| Confidence: ([\d.]+)%")
    skip_pattern = re.compile(r"(Skipping|Blocked|Reject): (.+)")
    error_pattern = re.compile(r"(ERROR|Exception|Traceback)")

    try:
        for line in sys.stdin:
            # LLM Decisions
            m_llm = llm_pattern.search(line)
            if m_llm:
                llm_decisions.append({
                    "decision": m_llm.group(1),
                    "confidence": float(m_llm.group(2))
                })

            # Skips
            m_skip = skip_pattern.search(line)
            if m_skip:
                skip_reasons.append(m_skip.group(2).strip())
                
            # Errors
            if error_pattern.search(line):
                errors.append(line.strip())
                
    except Exception as e:
        print(f"Error parsing logs: {e}")

    # Summary
    print(f"Total LLM Decisions: {len(llm_decisions)}")
    if llm_decisions:
        dec_counts = Counter(d['decision'] for d in llm_decisions)
        avg_conf = sum(d['confidence'] for d in llm_decisions) / len(llm_decisions)
        print(f"Decisions Breakdown: {dict(dec_counts)}")
        print(f"Average Confidence: {avg_conf:.2f}%")
        
    print(f"\nTop 5 Skip Reasons:")
    for reason, count in Counter(skip_reasons).most_common(5):
        print(f"  - {reason} ({count})")
        
    print(f"\nTotal Errors: {len(errors)}")
    print(f"Sample Errors:")
    for err in errors[:5]:
        print(f"  - {err[:100]}...")

if __name__ == "__main__":
    analyze()
